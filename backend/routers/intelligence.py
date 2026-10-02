"""
Intelligence endpoints: semantic search, Q&A, report generation,
document comparison, and domain detection.
"""
import re
import json
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from storage.store import get_result
import numpy as np

router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _require_result(doc_id: str):
    result = get_result(doc_id)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis results for {doc_id}. Run /api/analyze/{doc_id} first.",
        )
    return result


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


# ─── Semantic Search ──────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    min_score: float = 0.25


@router.post("/search/{doc_id}")
def semantic_search(doc_id: str, req: SearchRequest):
    """
    Semantic clause search using cosine similarity on MiniLM embeddings.
    Returns top-k most relevant clauses with similarity scores.
    """
    result = _require_result(doc_id)

    # Lazy-load embedder
    from pipeline.embedder import embed_texts
    from storage.store import load_embeddings

    # Full 384-d clause vectors are persisted during analysis — only the
    # query needs to be embedded per request.
    clause_vecs = load_embeddings(doc_id)
    if clause_vecs is None or len(clause_vecs) != len(result.clauses):
        raise HTTPException(
            status_code=422,
            detail="Stored embeddings missing for this document. Re-run analysis with /api/analyze/{doc_id}?force=true.",
        )

    try:
        query_vec = np.asarray(embed_texts([req.query])[0])  # shape (384,)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e}")

    clause_norms = np.linalg.norm(clause_vecs, axis=1)
    query_norm = np.linalg.norm(query_vec)
    denom = clause_norms * query_norm
    denom[denom == 0] = 1.0
    scores = ((clause_vecs @ query_vec) / denom).tolist()

    # Sort by score descending
    ranked = sorted(
        enumerate(result.clauses),
        key=lambda x: scores[x[0]],
        reverse=True,
    )

    hits = []
    for idx, clause in ranked[: req.top_k]:
        score = scores[idx]
        if score < req.min_score:
            break
        hits.append({
            "clause_id": clause.clause_id,
            "score": round(score, 4),
            "page": clause.page,
            "section": " > ".join(clause.section_hierarchy) if clause.section_hierarchy else "—",
            "text": clause.text,
            "text_preview": clause.text[:200],
            "entities": [e.model_dump() for e in clause.entities[:6]],
            "causal_count": len(clause.causal_patterns),
            "risk_tier": _clause_risk_tier(clause),
        })

    # Generate a simple answer synthesis from top-3 clauses
    answer = _synthesize_answer(req.query, hits[:3])

    return {
        "doc_id": doc_id,
        "query": req.query,
        "hits": hits,
        "answer": answer,
        "total_searched": len(result.clauses),
    }


def _clause_risk_tier(clause) -> str:
    tiers = [p.risk_tier for p in clause.causal_patterns]
    if "CRITICAL" in tiers:
        return "CRITICAL"
    if "HIGH" in tiers:
        return "HIGH"
    if "MEDIUM" in tiers:
        return "MEDIUM"
    return "LOW"


def _synthesize_answer(query: str, hits: list[dict]) -> str:
    """Create a simple extractive answer from the top matching clauses."""
    if not hits:
        return "No relevant clauses found for this query."

    best = hits[0]
    score = best["score"]

    if score < 0.35:
        return (
            f"No highly relevant clauses found (best match: {score:.0%} similarity). "
            "Try rephrasing your query or use broader terms."
        )

    parts = []
    for h in hits[:3]:
        preview = h["text"][:300].strip()
        if not preview.endswith("."):
            preview = preview.rsplit(" ", 1)[0] + "…"
        parts.append(f"• §{h['section']} (p.{h['page']}): {preview}")

    return (
        f"Found {len(hits)} relevant clause(s). Most relevant ({score:.0%} match):\n\n"
        + "\n\n".join(parts)
    )


# ─── Report Generation ────────────────────────────────────────────────────────

@router.get("/report/{doc_id}")
async def generate_report(doc_id: str, fmt: str = Query("json", pattern="^(json|html)$")):
    """
    Generate a structured analysis report.
    fmt=json → machine-readable report dict
    fmt=html → standalone HTML report for download
    """
    result = _require_result(doc_id)
    from storage.store import get_meta
    meta = get_meta(doc_id)

    report = _build_report(doc_id, result, meta)

    if fmt == "html":
        html = _render_html_report(report)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(
            content=html,
            headers={"Content-Disposition": f'attachment; filename="prism_report_{doc_id[:8]}.html"'},
        )

    return report


def _build_report(doc_id: str, result, meta) -> dict:
    clauses = result.clauses

    # ── Entity inventory
    entity_inv: dict[str, list[dict]] = {}
    for c in clauses:
        for e in c.entities:
            if e.label not in entity_inv:
                entity_inv[e.label] = []
            # Deduplicate by text
            if not any(x["text"] == e.text for x in entity_inv[e.label]):
                entity_inv[e.label].append({
                    "text": e.text,
                    "confidence": e.confidence,
                    "clause_id": c.clause_id,
                    "page": c.page,
                })

    # Sort each label by confidence desc
    for label in entity_inv:
        entity_inv[label].sort(key=lambda x: {"HIGH": 3, "MEDIUM": 2, "LOW": 1}[x["confidence"]], reverse=True)

    # ── Causal analysis
    all_patterns = []
    for c in clauses:
        for p in c.causal_patterns:
            all_patterns.append({
                **p.model_dump(),
                "section": " > ".join(c.section_hierarchy) if c.section_hierarchy else "—",
                "page": c.page,
            })

    # Risk matrix
    risk_matrix = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for p in all_patterns:
        risk_matrix[p["risk_tier"]].append(p)

    # ── Key obligations
    obligations = []
    for c in clauses:
        ob_entities = [e for e in c.entities if e.label == "OBLIGATION"]
        if ob_entities:
            obligations.append({
                "clause_id": c.clause_id,
                "page": c.page,
                "section": " > ".join(c.section_hierarchy) if c.section_hierarchy else "—",
                "text_preview": c.text[:250],
                "obligation_phrases": [e.text for e in ob_entities],
                "has_penalty": any(e.label == "PENALTY" for e in c.entities),
            })

    # ── Stats
    stats = result.stats
    entity_counts = stats.get("entity_type_counts", {})

    # Domain
    domain = _detect_domain(clauses)

    return {
        "doc_id": doc_id,
        "filename": meta.filename if meta else "Unknown",
        "domain": domain,
        "generated_at": _now_iso(),
        "executive_summary": {
            "total_clauses": len(clauses),
            "total_entities": stats.get("total_entities", 0),
            "causal_patterns": stats.get("causal_patterns_found", 0),
            "critical_risks": len(risk_matrix["CRITICAL"]),
            "high_risks": len(risk_matrix["HIGH"]),
            "total_pages": stats.get("total_pages", 0),
            "domain": domain,
        },
        "entity_inventory": entity_inv,
        "entity_counts": entity_counts,
        "causal_analysis": {
            "total": len(all_patterns),
            "by_type": {
                "IF_THEN": sum(1 for p in all_patterns if p["pattern_type"] == "IF_THEN"),
                "CONDITION_ACTION": sum(1 for p in all_patterns if p["pattern_type"] == "CONDITION_ACTION"),
                "PENALTY_TRIGGER": sum(1 for p in all_patterns if p["pattern_type"] == "PENALTY_TRIGGER"),
            },
            "risk_matrix": risk_matrix,
        },
        "key_obligations": obligations[:20],
        "compliance_checklist": _build_checklist(obligations, risk_matrix),
        "graph_summary": {
            "nodes": stats.get("graph_nodes", 0),
            "edges": stats.get("graph_edges", 0),
        },
    }


def _build_checklist(obligations: list, risk_matrix: dict) -> list[dict]:
    items = []
    for p in risk_matrix["CRITICAL"][:5]:
        items.append({
            "priority": "CRITICAL",
            "item": f"Address penalty trigger in §{p['section']}: {p['condition_span'][:120]}",
            "action": p["action_span"][:120],
        })
    for p in risk_matrix["HIGH"][:5]:
        items.append({
            "priority": "HIGH",
            "item": f"Review high-risk clause in §{p['section']}: {p['condition_span'][:120]}",
            "action": p["action_span"][:120],
        })
    for ob in obligations[:5]:
        if ob["has_penalty"]:
            items.append({
                "priority": "HIGH",
                "item": f"Obligation with penalty — §{ob['section']}, p.{ob['page']}",
                "action": "; ".join(ob["obligation_phrases"][:3]),
            })
    return items


def _detect_domain(clauses) -> str:
    """Detect legal domain from entity and keyword patterns."""
    text_sample = " ".join(c.text[:200] for c in clauses[:50]).lower()

    domain_signals = {
        "Income Tax": ["income tax", "assessment year", "taxable income", "deduction", "tds", "assessee", "itr"],
        "Labor Law": ["employee", "employer", "wages", "termination", "dismissal", "grievance", "trade union"],
        "Environment": ["pollution", "emission", "environmental", "waste", "discharge", "ecology"],
        "Procurement": ["tender", "procurement", "bidder", "contract award", "rfp", "purchase order"],
        "Competition Law": ["monopoly", "cartel", "dominant position", "anti-competitive", "merger"],
        "Data Protection": ["personal data", "data subject", "controller", "processor", "gdpr", "privacy"],
    }

    scores: dict[str, int] = {}
    for domain, signals in domain_signals.items():
        scores[domain] = sum(1 for s in signals if s in text_sample)

    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] >= 2 else "General Legislation"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _render_html_report(report: dict) -> str:
    es = report["executive_summary"]
    domain = report["domain"]
    filename = report["filename"]
    generated = report["generated_at"]

    checklist_rows = "".join(
        f"""<tr>
          <td><span class="badge badge-{item['priority'].lower()}">{item['priority']}</span></td>
          <td>{item['item']}</td>
          <td>{item['action']}</td>
        </tr>"""
        for item in report["compliance_checklist"]
    )

    risk = report["causal_analysis"]["risk_matrix"]
    risk_rows = ""
    for tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        for p in risk[tier][:3]:
            risk_rows += f"""<tr>
              <td><span class="badge badge-{tier.lower()}">{tier}</span></td>
              <td>{p.get('section','—')}</td>
              <td>{p['condition_span'][:120]}…</td>
              <td>{p['action_span'][:120]}…</td>
            </tr>"""

    entity_rows = ""
    for label, items in report["entity_inventory"].items():
        for e in items[:3]:
            entity_rows += f"""<tr>
              <td><span class="ent-{label.lower()}">{label}</span></td>
              <td>{e['text']}</td>
              <td>{e['confidence']}</td>
              <td>p.{e['page']}</td>
            </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>PRISM Report — {filename}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0D0907; color: #F0E0CC; margin: 0; padding: 0; }}
  .container {{ max-width: 960px; margin: 0 auto; padding: 40px 24px; }}
  h1 {{ font-size: 2rem; color: #F0A854; margin-bottom: 4px; }}
  h2 {{ font-size: 1.1rem; color: #C4762A; border-bottom: 1px solid #3D2A18;
        padding-bottom: 8px; margin-top: 32px; }}
  .meta {{ font-size: 0.75rem; color: #66493A; font-family: monospace; margin-bottom: 32px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
                  gap: 12px; margin: 20px 0; }}
  .stat {{ background: rgba(196,118,42,0.06); border: 1px solid rgba(196,118,42,0.20);
            border-radius: 12px; padding: 16px; text-align: center; }}
  .stat-value {{ font-size: 2rem; font-weight: 700; color: #F0A854; }}
  .stat-label {{ font-size: 0.65rem; font-family: monospace; color: #66493A;
                  text-transform: uppercase; letter-spacing: 0.08em; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.82rem; }}
  th {{ text-align: left; padding: 8px 12px; background: rgba(196,118,42,0.08);
        color: #A89278; font-family: monospace; font-size: 0.7rem;
        text-transform: uppercase; letter-spacing: 0.06em; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #2A1A0E; vertical-align: top; color: #C6A888; }}
  .badge {{ display: inline-block; font-family: monospace; font-size: 0.65rem;
             font-weight: 700; padding: 2px 7px; border-radius: 999px; }}
  .badge-critical {{ background: rgba(196,88,88,0.15); color: #E08A8A;
                      border: 1px solid rgba(196,88,88,0.3); }}
  .badge-high     {{ background: rgba(196,118,42,0.15); color: #E09830;
                      border: 1px solid rgba(196,118,42,0.3); }}
  .badge-medium   {{ background: rgba(90,158,200,0.15); color: #82B8D8;
                      border: 1px solid rgba(90,158,200,0.3); }}
  .badge-low      {{ background: rgba(106,170,106,0.15); color: #6AAA6A;
                      border: 1px solid rgba(106,170,106,0.3); }}
  .ent-obligation {{ color: #6AAA6A; font-weight: 600; }}
  .ent-penalty    {{ color: #E08A8A; font-weight: 600; }}
  .ent-right      {{ color: #82B8D8; font-weight: 600; }}
  .ent-threshold  {{ color: #F0A854; font-weight: 600; }}
  .ent-actor      {{ color: #C4762A; font-weight: 600; }}
  .ent-beneficiary{{ color: #9F78CC; font-weight: 600; }}
  .domain-tag {{ display: inline-block; background: rgba(139,92,246,0.12);
                  border: 1px solid rgba(139,92,246,0.25); color: #A78BFA;
                  font-family: monospace; font-size: 0.7rem; padding: 3px 10px;
                  border-radius: 999px; margin-left: 8px; }}
  footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid #3D2A18;
             font-size: 0.7rem; font-family: monospace; color: #3A2818;
             text-align: center; }}
</style>
</head>
<body>
<div class="container">
  <h1>PRISM Analysis Report <span class="domain-tag">{domain}</span></h1>
  <div class="meta">
    Document: {filename} &nbsp;|&nbsp; Generated: {generated} &nbsp;|&nbsp; ID: {report['doc_id'][:12]}
  </div>

  <h2>Executive Summary</h2>
  <div class="stats-grid">
    <div class="stat"><div class="stat-value">{es['total_clauses']}</div><div class="stat-label">Clauses</div></div>
    <div class="stat"><div class="stat-value">{es['total_entities']}</div><div class="stat-label">Entities</div></div>
    <div class="stat"><div class="stat-value">{es['causal_patterns']}</div><div class="stat-label">Causal Structures</div></div>
    <div class="stat"><div class="stat-value" style="color:#E08A8A">{es['critical_risks']}</div><div class="stat-label">Critical Risks</div></div>
    <div class="stat"><div class="stat-value" style="color:#E09830">{es['high_risks']}</div><div class="stat-label">High Risks</div></div>
    <div class="stat"><div class="stat-value">{es['total_pages']}</div><div class="stat-label">Pages</div></div>
  </div>

  <h2>Compliance Checklist</h2>
  <table>
    <tr><th>Priority</th><th>Item</th><th>Required Action</th></tr>
    {checklist_rows or '<tr><td colspan="3" style="color:#66493A">No compliance items extracted.</td></tr>'}
  </table>

  <h2>Risk Matrix — Causal Patterns</h2>
  <table>
    <tr><th>Risk</th><th>Section</th><th>Condition</th><th>Consequence</th></tr>
    {risk_rows or '<tr><td colspan="4" style="color:#66493A">No causal patterns found.</td></tr>'}
  </table>

  <h2>Entity Inventory (Sample)</h2>
  <table>
    <tr><th>Type</th><th>Text</th><th>Confidence</th><th>Page</th></tr>
    {entity_rows or '<tr><td colspan="4" style="color:#66493A">No entities found.</td></tr>'}
  </table>

  <footer>
    Generated by PRISM · Legal Cognition Engine · Phase 1 · FYP 2025-26
  </footer>
</div>
</body>
</html>"""


# ─── Document Comparison ──────────────────────────────────────────────────────

class CompareRequest(BaseModel):
    doc_id_a: str
    doc_id_b: str


@router.post("/compare")
def compare_documents(req: CompareRequest):
    """
    Compare two analyzed documents.
    Returns: new/removed obligations, entity deltas, shared vs unique entities.
    """
    result_a = _require_result(req.doc_id_a)
    result_b = _require_result(req.doc_id_b)
    from storage.store import get_meta
    meta_a = get_meta(req.doc_id_a)
    meta_b = get_meta(req.doc_id_b)

    def _entity_set(result) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for c in result.clauses:
            for e in c.entities:
                out.setdefault(e.label, set()).add(e.text.lower().strip())
        return out

    ents_a = _entity_set(result_a)
    ents_b = _entity_set(result_b)

    all_labels = set(ents_a) | set(ents_b)
    entity_delta: dict[str, dict] = {}
    for label in all_labels:
        a_set = ents_a.get(label, set())
        b_set = ents_b.get(label, set())
        entity_delta[label] = {
            "only_in_a": sorted(a_set - b_set)[:10],
            "only_in_b": sorted(b_set - a_set)[:10],
            "shared": sorted(a_set & b_set)[:10],
            "count_a": len(a_set),
            "count_b": len(b_set),
        }

    # Causal pattern comparison
    def _risk_counts(result) -> dict[str, int]:
        counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for c in result.clauses:
            for p in c.causal_patterns:
                counts[p.risk_tier] = counts.get(p.risk_tier, 0) + 1
        return counts

    risk_a = _risk_counts(result_a)
    risk_b = _risk_counts(result_b)

    # Obligation similarity (simple keyword overlap)
    ob_texts_a = set()
    ob_texts_b = set()
    for c in result_a.clauses:
        if any(e.label == "OBLIGATION" for e in c.entities):
            ob_texts_a.add(c.text[:100].lower().strip())
    for c in result_b.clauses:
        if any(e.label == "OBLIGATION" for e in c.entities):
            ob_texts_b.add(c.text[:100].lower().strip())

    # Domain
    domain_a = _detect_domain(result_a.clauses)
    domain_b = _detect_domain(result_b.clauses)

    # Clause-level diff via stored embeddings (Phase 2, Module D)
    clause_diff = _clause_level_diff(req.doc_id_a, req.doc_id_b, result_a, result_b)

    # Entities present in B but not in A (new obligations/penalties etc.)
    new_entities = []
    seen_new: set[tuple[str, str]] = set()
    for c in result_b.clauses:
        for e in c.entities:
            key = (e.label, e.text.lower().strip())
            if key[1] not in ents_a.get(e.label, set()) and key not in seen_new:
                seen_new.add(key)
                new_entities.append({"label": e.label, "text": e.text, "clause_id": c.clause_id})
    new_entities = new_entities[:50]

    # LLM causal rules present in B's added/modified clauses (when extracted)
    new_causal_rules = []
    if clause_diff:
        changed_b_ids = set(clause_diff["added"]) | {
            pair["clause_b_id"] for pair in clause_diff["modified"]
        }
        for c in result_b.clauses:
            if (
                c.clause_id in changed_b_ids
                and c.llm_extraction is not None
                and c.llm_extraction.is_causal
            ):
                new_causal_rules.append({
                    "clause_id": c.clause_id,
                    **c.llm_extraction.model_dump(),
                })

    return {
        "clause_diff": clause_diff,
        "new_entities": new_entities,
        "new_causal_rules": new_causal_rules,
        "doc_a": {"doc_id": req.doc_id_a, "filename": meta_a.filename if meta_a else req.doc_id_a,
                  "clauses": len(result_a.clauses), "entities": result_a.stats.get("total_entities", 0),
                  "domain": domain_a, "risk_counts": risk_a},
        "doc_b": {"doc_id": req.doc_id_b, "filename": meta_b.filename if meta_b else req.doc_id_b,
                  "clauses": len(result_b.clauses), "entities": result_b.stats.get("total_entities", 0),
                  "domain": domain_b, "risk_counts": risk_b},
        "entity_delta": entity_delta,
        "obligation_summary": {
            "obligations_in_a": len(ob_texts_a),
            "obligations_in_b": len(ob_texts_b),
            "delta": len(ob_texts_b) - len(ob_texts_a),
        },
        "risk_comparison": {
            "a": risk_a,
            "b": risk_b,
            "delta": {k: risk_b.get(k, 0) - risk_a.get(k, 0) for k in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
        },
    }


_DIFF_MATCHED_THRESHOLD = 0.92
_DIFF_MODIFIED_THRESHOLD = 0.75


def _clause_level_diff(doc_id_a: str, doc_id_b: str, result_a, result_b):
    """
    Clause-level diff between two documents via stored MiniLM embeddings.
    Mutual-best greedy matching: a pair counts only when each clause is the
    other's argmax. sim >= 0.92 → matched, 0.75–0.92 → modified; unmatched
    clauses are removed (A only) / added (B only).

    Returns None when either document lacks stored embeddings (pre-fix
    analyses) — the response then simply omits clause-level detail.
    """
    from storage.store import load_embeddings

    vecs_a = load_embeddings(doc_id_a)
    vecs_b = load_embeddings(doc_id_b)
    if (
        vecs_a is None or vecs_b is None
        or len(vecs_a) != len(result_a.clauses)
        or len(vecs_b) != len(result_b.clauses)
    ):
        return None

    norms_a = np.linalg.norm(vecs_a, axis=1, keepdims=True)
    norms_b = np.linalg.norm(vecs_b, axis=1, keepdims=True)
    norms_a[norms_a == 0] = 1.0
    norms_b[norms_b == 0] = 1.0
    sim = (vecs_a / norms_a) @ (vecs_b / norms_b).T  # (len_a, len_b)

    best_for_a = sim.argmax(axis=1)
    best_for_b = sim.argmax(axis=0)

    matched = 0
    modified: list[dict] = []
    paired_a: set[int] = set()
    paired_b: set[int] = set()

    for i, j in enumerate(best_for_a):
        if best_for_b[j] != i:
            continue  # not a mutual best match
        similarity = float(sim[i, j])
        if similarity < _DIFF_MODIFIED_THRESHOLD:
            continue
        paired_a.add(i)
        paired_b.add(int(j))
        if similarity >= _DIFF_MATCHED_THRESHOLD:
            matched += 1
        else:
            modified.append({
                "clause_a_id": result_a.clauses[i].clause_id,
                "clause_b_id": result_b.clauses[int(j)].clause_id,
                "similarity": round(similarity, 4),
            })

    return {
        "matched": matched,
        "modified": modified,
        "added": [c.clause_id for k, c in enumerate(result_b.clauses) if k not in paired_b],
        "removed": [c.clause_id for k, c in enumerate(result_a.clauses) if k not in paired_a],
        "thresholds": {
            "matched": _DIFF_MATCHED_THRESHOLD,
            "modified": _DIFF_MODIFIED_THRESHOLD,
        },
    }


# ─── Domain Detection ─────────────────────────────────────────────────────────

@router.get("/domain/{doc_id}")
async def get_domain(doc_id: str):
    result = _require_result(doc_id)
    domain = _detect_domain(result.clauses)
    return {"doc_id": doc_id, "domain": domain}
