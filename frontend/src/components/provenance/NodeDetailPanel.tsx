"use client";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, FileText, Hash, Zap, Network, BookOpen, Scale, AlertTriangle,
  Users, Shield, TrendingUp, Layers, Info, Sparkles, ExternalLink,
} from "lucide-react";
import type { GraphNode } from "@/types";
import { NODE_TYPE_COLORS, ENTITY_COLORS } from "@/lib/colors";
import { tokens, alpha, riskStyle } from "@/lib/tokens";
import type { EntityLabel } from "@/types";

// ── Data-driven per-node explanations ─────────────────────────────────────────
// Each explanation opens with a short generic lead for the node type, then
// appends detail read from THIS node's actual data — so no two nodes read alike.

function num(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}
function str(v: unknown): string | undefined {
  return typeof v === "string" && v.trim() ? v.trim() : undefined;
}

function buildExplanation(node: GraphNode): { title: string; body: string } {
  const d = node.data;

  switch (node.type) {
    case "document": {
      const clauses = num(d.clause_count);
      return {
        title: "Root document",
        body: clauses != null
          ? `Provenance root for this analysis. Every one of the ${clauses} extracted clause${clauses === 1 ? "" : "s"} — and all entities, causal links, and risk scores derived from them — traces back to this node.`
          : "Provenance root — every chapter, section, clause, entity, and causal link in this analysis traces back here.",
      };
    }

    case "chapter": {
      const n = str(d.number);
      return {
        title: "Chapter division",
        body: n
          ? `Chapter ${n} — a top-level division grouping related sections by subject. Expand its children to see the provisions it contains.`
          : "A top-level structural division grouping related sections and clauses by subject.",
      };
    }

    case "section": {
      const n = str(d.number);
      return {
        title: "Numbered section",
        body: n
          ? `Section §${n} — a discrete, self-contained statutory provision. Its connected clause nodes hold the exact extracted text.`
          : "A discrete statutory provision within a chapter; its clause nodes hold the exact text.",
      };
    }

    case "clause": {
      const page = num(d.page);
      const entities = num(d.entity_count);
      const complexity = num(d.complexity_score);
      const preview = str(d.text_preview);
      const facts: string[] = [];
      if (page != null) facts.push(`sits on page ${page}`);
      if (entities != null) facts.push(`carries ${entities} extracted entit${entities === 1 ? "y" : "ies"}`);
      if (complexity != null) facts.push(`scores ${complexity.toFixed(2)} on structural complexity`);
      const parts = ["A semantically complete clause processed independently through NER and causal detection."];
      if (facts.length) parts.push(`This one ${facts.join(", ")}.`);
      if (preview) parts.push(`It begins: “${preview}”`);
      return { title: "Extracted clause", body: parts.join(" ") };
    }

    case "entity": {
      const label = str(d.label);
      const text = str(d.text);
      const freq = num(d.frequency);
      const parts: string[] = [];
      if (label && text) parts.push(`“${text}” was extracted here as a ${label} entity.`);
      else if (label) parts.push(`A ${label} entity extracted from the document.`);
      else parts.push("A named legal concept extracted from the document.");
      parts.push(
        freq != null && freq > 1
          ? `It recurs across ${freq} clauses, so it is a shared concept the graph links wherever it appears — not a one-off mention.`
          : "It appears in this clause."
      );
      return { title: "Legal entity", body: parts.join(" ") };
    }

    case "causal": {
      const pt = str(d.pattern_type);
      const page = num(d.page);
      const condition = str(d.condition) ?? str(d.condition_span);
      const action = str(d.action) ?? str(d.action_span);
      const risk = str(d.risk_tier);
      const impact = num(d.impact_score);
      const conf = num(d.confidence);
      const ptLabel = pt ? pt.replace(/_/g, " ").toLowerCase() : "causal";
      const parts = [`A ${ptLabel} pattern${page != null ? ` detected on page ${page}` : ""}.`];
      if (condition && action) parts.push(`It links the condition “${condition}” to the consequence “${action}”.`);
      else if (condition) parts.push(`Its triggering condition is “${condition}”.`);
      const scored: string[] = [];
      if (risk) scored.push(`${risk} risk tier`);
      if (impact != null) scored.push(`impact ${impact.toFixed(2)}`);
      if (conf != null) scored.push(`detector confidence ${Math.round(conf * 100)}%`);
      if (scored.length) parts.push(`Scored at ${scored.join(", ")}.`);
      return { title: "Causal pattern", body: parts.join(" ") };
    }
  }

  return { title: node.type, body: "" };
}

const ENTITY_TYPE_MEANING: Record<string, { icon: React.ElementType; color: string; description: string }> = {
  OBLIGATION:  { icon: Scale,         color: tokens.entity.OBLIGATION.text,  description: "Marks a legal duty. The subject is required to act or refrain from acting under law." },
  PENALTY:     { icon: AlertTriangle, color: tokens.entity.PENALTY.text,     description: "Marks a punishable consequence — fine, imprisonment, or civil liability for non-compliance." },
  RIGHT:       { icon: Shield,        color: tokens.entity.RIGHT.text,       description: "Marks an entitlement or protection granted to a party under this provision." },
  THRESHOLD:   { icon: TrendingUp,    color: tokens.entity.THRESHOLD.text,   description: "Marks a numeric limit, monetary value, or qualifying condition that triggers other provisions." },
  ACTOR:       { icon: Users,         color: tokens.entity.ACTOR.text,       description: "An authority, officer, or responsible party named in the provision — typically enforces or administers rules." },
  BENEFICIARY: { icon: BookOpen,      color: tokens.entity.BENEFICIARY.text, description: "A party that receives an exemption, concession, or legal benefit under this provision." },
};

const RISK_STYLE: Record<string, { color: string; bg: string }> = {
  CRITICAL: { color: riskStyle("CRITICAL").text, bg: alpha(riskStyle("CRITICAL").base, 0.12) },
  HIGH:     { color: riskStyle("HIGH").text,     bg: alpha(riskStyle("HIGH").base, 0.12) },
  MEDIUM:   { color: riskStyle("MEDIUM").text,   bg: alpha(riskStyle("MEDIUM").base, 0.1) },
  LOW:      { color: riskStyle("LOW").text,      bg: alpha(riskStyle("LOW").base, 0.1) },
};

const TYPE_ICONS: Record<string, React.ElementType> = {
  document: FileText,
  chapter:  Hash,
  section:  Hash,
  clause:   FileText,
  entity:   Network,
  causal:   Zap,
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function DataRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-[9px] font-mono uppercase tracking-widest mb-1 text-text-dim">
        {label}
      </p>
      <div className="rounded-lg px-2.5 py-1.5 bg-bg-surface/80 border border-border">
        {typeof value === "string" ? (
          <p className="text-xs font-mono text-text-secondary">
            {value}
          </p>
        ) : (
          value
        )}
      </div>
    </div>
  );
}

function TextBlock({ label, text }: { label: string; text: string }) {
  return (
    <div>
      <p className="text-[9px] font-mono uppercase tracking-widest mb-1 text-text-dim">
        {label}
      </p>
      <div className="rounded-lg px-2.5 py-2 bg-bg-surface/80 border border-border">
        <p className="text-xs leading-relaxed text-text-secondary">
          {text}
        </p>
      </div>
    </div>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 75 ? tokens.status.success : pct >= 45 ? tokens.status.warning : tokens.status.error;
  return (
    <div className="flex items-center gap-2">
      <div
        className="flex-1 rounded-full overflow-hidden bg-bg-surface/80"
        style={{ height: 4 }}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, background: color, transition: "width 0.4s" }}
        />
      </div>
      <span className="text-[10px] font-mono" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

function EntityPill({ label, text }: { label: string; text?: string }) {
  const ec = ENTITY_COLORS[label as EntityLabel];
  return (
    <span
      className="inline-flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.5 rounded"
      style={{
        background: ec?.bg ?? alpha(tokens.accent.primary, 0.12),
        color: ec?.text ?? tokens.text.secondary,
        border: `1px solid ${ec?.border ?? alpha(tokens.accent.primary, 0.3)}`,
      }}
    >
      {text ? `${label}: ${text.slice(0, 18)}` : label}
    </span>
  );
}

function ExplainerCard({
  title,
  body,
  color,
}: {
  title: string;
  body: string;
  color: string;
}) {
  return (
    <div
      className="rounded-xl p-3 space-y-1.5"
      style={{
        background: `${color}08`,
        border: `1px solid ${color}22`,
      }}
    >
      <div className="flex items-center gap-1.5">
        <Info className="w-3 h-3" style={{ color }} />
        <p
          className="text-[9px] font-mono uppercase tracking-widest"
          style={{ color }}
        >
          {title}
        </p>
      </div>
      <p className="text-[10px] leading-relaxed text-text-secondary">
        {body}
      </p>
    </div>
  );
}

/** Deep-link to the Explainability Studio for a clause's LIME + LLM breakdown.
 *  Closes the gap that the provenance graph never linked out to XAI. */
function ExplainLink({ docId, clauseId }: { docId?: string; clauseId?: string }) {
  if (!docId || !clauseId) return null;
  return (
    <Link
      href={`/explain/${docId}/${clauseId}`}
      className="inline-flex items-center gap-1.5 text-[10px] font-mono text-accent-primary hover:underline"
    >
      <Sparkles className="w-3 h-3" /> View LIME explanation <ExternalLink className="w-3 h-3" />
    </Link>
  );
}

// ── Per-type rich content ─────────────────────────────────────────────────────

function NodeContent({ node, docId }: { node: GraphNode; docId?: string }) {
  const d = node.data;
  const expl = buildExplanation(node);

  // ── CLAUSE ──────────────────────────────────────────────────────────────────
  if (node.type === "clause") {
    const entityCount = (d.entity_count as number) ?? 0;
    const causalCount = (d.causal_count as number) ?? 0;
    const complexity = (d.complexity_score as number) ?? 0;
    const riskTier = d.risk_tier as string | undefined;
    const section = (d.section_hierarchy as string[])?.slice(-1)[0];

    return (
      <div className="space-y-3">
        {section && (
          <div className="flex items-center gap-1.5">
            <Layers className="w-3 h-3 flex-shrink-0 text-text-dim" />
            <p className="text-[10px] font-mono text-text-muted">
              {section}
            </p>
          </div>
        )}

{Boolean(d.text_preview) && (
          <TextBlock label="Clause text" text={String(d.text_preview)} />
        )}

        <div className="grid grid-cols-3 gap-2 text-center">
          {[
            { label: "Entities", value: entityCount, color: tokens.status.success },
            { label: "Causal", value: causalCount, color: tokens.accent.primary },
            {
              label: "Complexity",
              value: complexity.toFixed ? complexity.toFixed(2) : complexity,
              color: tokens.text.secondary,
            },
          ].map((s) => (
            <div
              key={s.label}
              className="rounded-lg py-2 bg-bg-surface/80 border border-border"
            >
              <p className="font-bold text-sm" style={{ color: s.color }}>
                {s.value}
              </p>
              <p className="text-[8px] font-mono uppercase mt-0.5 text-text-dim">
                {s.label}
              </p>
            </div>
          ))}
        </div>

        {riskTier && (
          <div
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg"
            style={{
              background: RISK_STYLE[riskTier]?.bg ?? alpha(tokens.bg.surface, 0.6),
              border: `1px solid ${RISK_STYLE[riskTier]?.color ?? tokens.accent.primary}40`,
            }}
          >
            <AlertTriangle className="w-3 h-3 flex-shrink-0" style={{ color: RISK_STYLE[riskTier]?.color ?? tokens.accent.primary }} />
            <span className="text-[10px] font-mono" style={{ color: RISK_STYLE[riskTier]?.color ?? tokens.accent.primary }}>
              {riskTier} risk tier
            </span>
          </div>
        )}

        <ExplainerCard
          title="What this clause represents"
          body={expl.body}
          color={tokens.text.secondary}
        />

        <ExplainLink docId={docId} clauseId={node.id} />
      </div>
    );
  }

  // ── ENTITY ──────────────────────────────────────────────────────────────────
  if (node.type === "entity") {
    const label = d.label as string;
    const freq = (d.frequency as number) ?? 1;
    const meta = ENTITY_TYPE_MEANING[label];
    const MetaIcon = meta?.icon ?? Network;

    return (
      <div className="space-y-3">
        {label && (
          <div className="flex items-center gap-2">
            <EntityPill label={label} text={node.label} />
            {freq > 1 && (
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-accent-primary/10 border border-accent-primary/20 text-accent-primary">
                ×{freq} clauses
              </span>
            )}
          </div>
        )}

        {meta && (
          <div
            className="flex items-start gap-3 p-3 rounded-xl"
            style={{ background: `${meta.color}08`, border: `1px solid ${meta.color}22` }}
          >
            <div
              className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: `${meta.color}18`, border: `1px solid ${meta.color}35` }}
            >
              <MetaIcon className="w-3.5 h-3.5" style={{ color: meta.color }} />
            </div>
            <div>
              <p className="text-[9px] font-mono uppercase tracking-widest mb-0.5" style={{ color: meta.color }}>
                {label}
              </p>
              <p className="text-[10px] leading-relaxed text-text-secondary">
                {meta.description}
              </p>
            </div>
          </div>
        )}

        <ExplainerCard
          title="Why this node exists"
          body={expl.body}
          color={meta?.color ?? tokens.accent.primary}
        />

        {(d.confidence as string) && (
          <div>
            <p className="text-[9px] font-mono uppercase tracking-widest mb-1 text-text-dim">
              Extraction confidence
            </p>
            <ConfidenceBar
              value={
                (d.confidence as string) === "HIGH"
                  ? 0.9
                  : (d.confidence as string) === "MEDIUM"
                  ? 0.55
                  : 0.25
              }
            />
            <p className="text-[9px] font-mono mt-1 text-text-dim">
              {(d.confidence as string) === "HIGH"
                ? "Matched a highly specific legal pattern"
                : (d.confidence as string) === "MEDIUM"
                ? "Matched a broad indicator pattern"
                : "Weak pattern match — review recommended"}
            </p>
          </div>
        )}
      </div>
    );
  }

  // ── CAUSAL ───────────────────────────────────────────────────────────────────
  if (node.type === "causal") {
    const patternType = d.pattern_type as string;
    const riskTier = d.risk_tier as string | undefined;
    const impactScore = d.impact_score as number | undefined;
    const condition = d.condition_span as string | undefined;
    const action = d.action_span as string | undefined;

    const patternDesc: Record<string, string> = {
      IF_THEN:          "A conditional trigger: a specified condition activates a defined legal outcome.",
      CONDITION_ACTION: "A subject-to clause: fulfilment of a prerequisite enables or restricts an action.",
      PENALTY_TRIGGER:  "An enforcement mechanism: a described offence triggers a punishable consequence.",
    };

    return (
      <div className="space-y-3">
        {patternType && (
          <div
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-mono"
            style={{
              background: alpha(tokens.node.causal, 0.1),
              border: `1px solid ${alpha(tokens.node.causal, 0.25)}`,
              color: tokens.node.causal,
            }}
          >
            <Zap className="w-3 h-3" />
            {patternType.replace(/_/g, " ")}
          </div>
        )}

        {patternDesc[patternType] && (
          <p className="text-xs leading-relaxed text-text-secondary">
            {patternDesc[patternType]}
          </p>
        )}

        {condition && <TextBlock label="Condition" text={condition} />}
        {action && <TextBlock label="Consequence" text={action} />}

        {riskTier && (
          <div className="flex items-center justify-between">
            <DataRow
              label="Risk tier"
              value={
                <span
                  className="text-xs font-bold"
                  style={{ color: RISK_STYLE[riskTier]?.color ?? tokens.accent.primary }}
                >
                  {riskTier}
                </span>
              }
            />
            {impactScore !== undefined && (
              <div className="ml-3 flex-1">
                <p className="text-[9px] font-mono uppercase tracking-widest mb-1 text-text-dim">
                  Impact score
                </p>
                <ConfidenceBar value={impactScore} />
              </div>
            )}
          </div>
        )}

        <ExplainerCard
          title="Why this matters"
          body={expl.body}
          color={tokens.node.causal}
        />

        <ExplainLink docId={docId} clauseId={d.source_clause_id as string | undefined} />
      </div>
    );
  }

  // ── DOCUMENT / CHAPTER / SECTION — generic with data-driven explainer ─────
  const displayFields = Object.entries(d).filter(
    ([k, v]) => v !== undefined && v !== null && !["section_hierarchy"].includes(k)
  );

  return (
    <div className="space-y-3">
      {expl.body && (
        <ExplainerCard
          title={expl.title}
          body={expl.body}
          color={NODE_TYPE_COLORS[node.type] ?? tokens.accent.primary}
        />
      )}
      {displayFields.map(([key, value]) => {
        if (typeof value === "object") return null;
        return (
          <DataRow key={key} label={key.replace(/_/g, " ")} value={String(value)} />
        );
      })}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────
export default function NodeDetailPanel({
  node,
  onClose,
  docId,
}: {
  node: GraphNode | null;
  onClose: () => void;
  docId?: string;
}) {
  const typeColor = node ? (NODE_TYPE_COLORS[node.type] ?? tokens.accent.primary) : tokens.accent.primary;
  const Icon = node ? (TYPE_ICONS[node.type] ?? FileText) : FileText;

  return (
    <AnimatePresence>
      {node && (
        <motion.div
          key={node.id}
          initial={{ x: -320, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -320, opacity: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
          className="absolute top-0 left-0 bottom-0 z-20 overflow-y-auto bg-bg-deep/95 border-r border-border"
          style={{ width: 288 }}
        >
          {/* Header */}
          <div className="sticky top-0 flex items-center justify-between px-4 py-3 z-10 bg-bg-deep/95 border-b border-border">
            <div className="flex items-center gap-2.5 min-w-0">
              <div
                className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{
                  background: `${typeColor}18`,
                  border: `1px solid ${typeColor}35`,
                }}
              >
                <Icon className="w-3.5 h-3.5" style={{ color: typeColor }} />
              </div>
              <div className="min-w-0">
                <p
                  className="text-[9px] font-mono uppercase tracking-widest"
                  style={{ color: `${typeColor}99` }}
                >
                  {node.type}
                </p>
                <p
                  className="text-xs font-display font-semibold truncate text-text-primary"
                  style={{ maxWidth: 170 }}
                >
                  {node.label}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="flex-shrink-0 p-1 rounded-lg transition-colors text-text-dim hover:text-text-primary hover:bg-bg-surface/80"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Content */}
          <div className="p-4">
            <NodeContent node={node} docId={docId} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
