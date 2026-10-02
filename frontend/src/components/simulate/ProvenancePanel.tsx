"use client";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";
import { ChevronRight, ExternalLink, FileText, GitBranch, Loader2, Sparkles } from "lucide-react";
import { api, Phase2UnavailableError } from "@/lib/api";
import { alpha, tokens } from "@/lib/tokens";
import type { ProvenanceLink, SimulationProvenance } from "@/types";

/**
 * The headline provenance drill-down: for a completed simulation, trace each
 * active rule back to its source clause, LLM extraction, and LIME tokens.
 * The data spine (finding → active_rule clause_id → clause → LLM → LIME) is
 * joined server-side by GET /api/simulate/{doc}/provenance.
 */
export default function ProvenancePanel({
  docId,
  simulationId,
}: {
  docId: string;
  simulationId: string;
}) {
  const [prov, setProv] = useState<SimulationProvenance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setProv(null);
    setError(null);
    (async () => {
      try {
        const data = await api.getSimulationProvenance(docId, simulationId);
        if (!cancelled) setProv(data);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Phase2UnavailableError ? "offline" : e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docId, simulationId]);

  return (
    <div className="glass-card p-6">
      <div className="flex items-center gap-3 mb-1">
        <GitBranch className="w-4 h-4 text-accent-primary" />
        <p className="font-display text-sm text-text-primary">Provenance — trace every finding to its source</p>
        <span className="text-[10px] font-mono text-text-dim">outcome → rule → clause → LLM → LIME</span>
      </div>
      <p className="text-xs text-text-muted mb-4 max-w-2xl leading-relaxed">
        Each rule the simulation acted on links back to the exact statute clause that produced it,
        the LLM&apos;s structured reading of that clause, and the token-level explanation behind it.
      </p>

      {!prov && !error && (
        <div className="flex items-center gap-2 text-xs font-mono text-text-dim py-4">
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Joining provenance chain…
        </div>
      )}
      {error && (
        <p className="text-xs font-mono text-status-warning py-4">
          {error === "offline" ? "Provenance module offline." : error}
        </p>
      )}

      {prov && (
        <div className="space-y-2">
          {prov.chain.length === 0 && (
            <p className="text-xs font-mono text-text-dim">No traceable rules for this run.</p>
          )}
          {prov.chain.map((link) => (
            <ProvenanceRow
              key={link.clause_id}
              docId={docId}
              link={link}
              open={openId === link.clause_id}
              onToggle={() => setOpenId((id) => (id === link.clause_id ? null : link.clause_id))}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ProvenanceRow({
  docId,
  link,
  open,
  onToggle,
}: {
  docId: string;
  link: ProvenanceLink;
  open: boolean;
  onToggle: () => void;
}) {
  const sourceColor = link.rule?.source === "llm" ? tokens.status.success : tokens.accent.primary;
  const description = link.rule?.description || link.clause.text.slice(0, 90);

  return (
    <div className="rounded-lg border border-border overflow-hidden" style={{ background: alpha(tokens.bg.deep, 0.4) }}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-white/[0.02] transition-colors"
      >
        <ChevronRight
          className="w-3.5 h-3.5 text-text-dim transition-transform flex-shrink-0"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        />
        <span
          className="text-[9px] font-mono px-1.5 py-0.5 rounded flex-shrink-0"
          style={{ color: sourceColor, border: `1px solid ${alpha(sourceColor, 0.35)}`, background: alpha(sourceColor, 0.1) }}
        >
          {link.rule?.source === "llm" ? "LLM" : "RULE"}
        </span>
        <span className="text-xs text-text-secondary truncate flex-1">{description}</span>
        {link.matched_template && (
          <span className="text-[9px] font-mono text-text-dim flex-shrink-0" title="matched Module-C template">
            ⌘ {link.matched_template}
          </span>
        )}
        <span className="text-[9px] font-mono text-text-dim flex-shrink-0">p.{link.clause.page}</span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 pt-1 space-y-3 border-t border-border/60">
              {/* Source clause */}
              <div>
                <p className="kicker !text-[8px] mb-1 flex items-center gap-1.5">
                  <FileText className="w-3 h-3" /> Source clause · page {link.clause.page}
                  {link.clause.section_hierarchy.length > 0 && (
                    <span className="text-text-dim normal-case tracking-normal">
                      · {link.clause.section_hierarchy.join(" › ")}
                    </span>
                  )}
                </p>
                <p className="text-[11px] text-text-muted leading-relaxed max-h-28 overflow-y-auto">
                  {link.clause.text}
                </p>
              </div>

              {/* LLM reading */}
              {link.llm_extraction && (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <ExtractionField label="Condition" value={link.llm_extraction.condition} />
                  <ExtractionField label="Action" value={link.llm_extraction.action} />
                  <ExtractionField label="Consequence" value={link.llm_extraction.consequence} />
                </div>
              )}

              {/* LIME top tokens */}
              {link.lime && link.lime.top_tokens.length > 0 && (
                <div>
                  <p className="kicker !text-[8px] mb-1.5 flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3" /> Top LIME tokens
                    <span className="text-text-dim normal-case tracking-normal">({link.lime.mode})</span>
                    {typeof link.lime.fidelity === "number" && (
                      <span className="text-text-dim normal-case tracking-normal">
                        · fidelity {link.lime.fidelity.toFixed(2)}
                      </span>
                    )}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {link.lime.top_tokens.map(([tok, w], i) => {
                      const c = w >= 0 ? tokens.status.success : tokens.status.error;
                      return (
                        <span
                          key={`${tok}-${i}`}
                          className="text-[10px] font-mono px-1.5 py-0.5 rounded"
                          style={{ color: c, border: `1px solid ${alpha(c, 0.3)}`, background: alpha(c, 0.08) }}
                        >
                          {tok} {w >= 0 ? "+" : ""}{w.toFixed(2)}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}

              <Link
                href={`/explain/${docId}/${link.clause_id}`}
                className="inline-flex items-center gap-1.5 text-[10px] font-mono text-accent-primary hover:underline"
              >
                Open in Explainability Studio <ExternalLink className="w-3 h-3" />
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ExtractionField({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="rounded-md border border-border/60 p-2" style={{ background: alpha(tokens.bg.base, 0.5) }}>
      <p className="text-[8px] font-mono uppercase tracking-wider text-text-dim mb-0.5">{label}</p>
      <p className="text-[11px] text-text-secondary leading-snug">{value || <span className="text-text-dim">—</span>}</p>
    </div>
  );
}
