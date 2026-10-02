"use client";
import { forwardRef } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Zap, FileText, AlertTriangle, Bot, Sparkles, FlaskConical } from "lucide-react";
import type { Clause, Entity, RiskTier } from "@/types";
import { ENTITY_COLORS } from "@/lib/colors";
import { tokens, alpha, riskStyle } from "@/lib/tokens";

const ENTITY_LABEL_ORDER = ["OBLIGATION", "PENALTY", "RIGHT", "THRESHOLD", "ACTOR", "BENEFICIARY"] as const;

// Confidence dot: HIGH=solid, MEDIUM=semi, LOW=faint
const CONF_STYLES = {
  HIGH:   { background: "currentColor", opacity: 1,    title: "High confidence" },
  MEDIUM: { background: "currentColor", opacity: 0.55, title: "Medium confidence" },
  LOW:    { background: "currentColor", opacity: 0.25, title: "Low confidence" },
};

// Highest risk tier across all causal patterns in a clause
function clauseMaxRisk(clause: Clause): RiskTier | null {
  const order: RiskTier[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
  for (const tier of order) {
    if (clause.causal_patterns.some((p) => p.risk_tier === tier)) return tier;
  }
  return null;
}

const RISK_LABELS: Record<RiskTier, string> = {
  CRITICAL: "CRITICAL",
  HIGH: "HIGH RISK",
  MEDIUM: "MEDIUM",
  LOW: "LOW",
};

function EntityPill({ entity }: { entity: Entity }) {
  const colors = ENTITY_COLORS[entity.label] || ENTITY_COLORS["OBLIGATION"];
  const confStyle = CONF_STYLES[entity.confidence ?? "MEDIUM"];
  return (
    <span
      className="entity-pill inline-flex items-center gap-1"
      style={{
        background: colors.bg,
        color: colors.text,
        borderColor: colors.border,
      }}
      title={confStyle.title}
    >
      {/* Confidence dot */}
      <span
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{
          background: colors.text,
          opacity: confStyle.opacity,
        }}
      />
      {entity.label}
    </span>
  );
}

function HighlightedText({ text, entities }: { text: string; entities: Entity[] }) {
  if (!entities.length) {
    return <p className="text-sm leading-relaxed text-text-secondary">{text}</p>;
  }

  const sorted = [...entities].sort((a, b) => a.start - b.start);
  const parts: { text: string; entity?: Entity }[] = [];
  let cursor = 0;

  for (const entity of sorted) {
    if (entity.start < cursor) continue;
    if (entity.start > cursor) {
      parts.push({ text: text.slice(cursor, entity.start) });
    }
    parts.push({ text: text.slice(entity.start, entity.end), entity });
    cursor = entity.end;
  }
  if (cursor < text.length) {
    parts.push({ text: text.slice(cursor) });
  }

  return (
    <p className="text-sm leading-relaxed text-text-secondary">
      {parts.map((part, i) => {
        if (!part.entity) return <span key={i}>{part.text}</span>;
        const colors = ENTITY_COLORS[part.entity.label] || ENTITY_COLORS["OBLIGATION"];
        return (
          <mark
            key={i}
            style={{
              background: colors.bg,
              color: colors.text,
              borderRadius: "3px",
              padding: "0 2px",
            }}
          >
            {part.text}
          </mark>
        );
      })}
    </p>
  );
}

interface ClauseCardProps {
  clause: Clause;
  isSelected: boolean;
  onSelect: () => void;
}

// forwardRef: framer-motion's AnimatePresence popLayout hands the exit
// animation a ref to this card.
const ClauseCard = forwardRef<HTMLDivElement, ClauseCardProps>(function ClauseCard(
  { clause, isSelected, onSelect },
  ref
) {
  const entityCounts: Record<string, number> = {};
  for (const e of clause.entities) {
    entityCounts[e.label] = (entityCounts[e.label] || 0) + 1;
  }
  const uniqueLabels = ENTITY_LABEL_ORDER.filter((l) => entityCounts[l]);
  const hasCausal = clause.causal_patterns.length > 0;
  const maxRisk = clauseMaxRisk(clause);
  const maxRiskStyle = maxRisk ? riskStyle(maxRisk) : null;

  return (
    <motion.div
      ref={ref}
      layout
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      onClick={onSelect}
      className="group relative rounded-xl p-4 cursor-pointer transition-all duration-200"
      style={{
        background: isSelected ? alpha(tokens.accent.primary, 0.07) : alpha(tokens.bg.surface, 0.7),
        border: isSelected
          ? `1px solid ${alpha(tokens.accent.primary, 0.35)}`
          : `1px solid ${tokens.border.DEFAULT}`,
        boxShadow: isSelected ? `0 0 20px ${alpha(tokens.accent.primary, 0.08)}` : "none",
      }}
      whileHover={{
        borderColor: alpha(tokens.accent.primary, 0.25),
        background: alpha(tokens.bg.surface, 0.9),
      }}
    >
      {/* Top row: metadata */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-3.5 h-3.5 flex-shrink-0 text-text-muted" />
          <span className="text-[11px] font-mono truncate text-text-muted">
            {clause.section_hierarchy.length > 0
              ? `§ ${clause.section_hierarchy.join(".")}`
              : `Page ${clause.page}`}
          </span>
          <span className="text-text-dim">·</span>
          <span className="text-[11px] font-mono text-text-muted">p.{clause.page}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {/* Risk tier badge */}
          {maxRisk && maxRiskStyle && maxRisk !== "LOW" && (
            <motion.span
              animate={maxRisk === "CRITICAL" ? { opacity: [0.7, 1, 0.7] } : {}}
              transition={{ duration: 1.8, repeat: Infinity }}
              className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full"
              style={{
                background: alpha(maxRiskStyle.base, 0.12),
                border: `1px solid ${alpha(maxRiskStyle.base, 0.35)}`,
                color: maxRiskStyle.text,
              }}
            >
              {maxRisk === "CRITICAL" && <AlertTriangle style={{ width: 9, height: 9 }} />}
              {RISK_LABELS[maxRisk]}
            </motion.span>
          )}
          {hasCausal && (
            <span className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full bg-accent-primary/10 border border-accent-primary/30 text-accent-bright">
              <Zap style={{ width: 10, height: 10 }} />
              IF→THEN
            </span>
          )}
          {/* Phase 2: LLM extraction badge */}
          {clause.llm_extraction?.is_causal && (
            <span
              className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded-full"
              style={{
                background: alpha(tokens.status.info, 0.1),
                border: `1px solid ${alpha(tokens.status.info, 0.3)}`,
                color: tokens.status.info,
              }}
              title={`Phi-3.5-mini extraction · ${clause.extraction_method}`}
            >
              <Bot style={{ width: 10, height: 10 }} />
              LLM
            </span>
          )}
        </div>
      </div>

      {/* Text */}
      <div className="mb-3 line-clamp-3">
        <HighlightedText text={clause.text} entities={clause.entities} />
      </div>

      {/* Entity pills with confidence dots */}
      {uniqueLabels.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {uniqueLabels.map((label) => {
            const rep = clause.entities.find((e) => e.label === label)!;
            return <EntityPill key={label} entity={rep} />;
          })}
        </div>
      )}

      {/* Complexity bar */}
      {clause.complexity_score > 0 && (
        <div className="mt-3 flex items-center gap-2">
          <span className="text-[10px] font-mono text-text-dim">Density</span>
          <div className="flex-1 h-[2px] rounded-full bg-border">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.min(clause.complexity_score * 400, 100)}%`,
                background: `linear-gradient(90deg, ${tokens.accent.primary}, ${tokens.accent.bright})`,
              }}
            />
          </div>
        </div>
      )}

      {/* Phase 2 actions — revealed on hover/selection for causal clauses */}
      {(hasCausal || clause.llm_extraction?.is_causal) && (
        <div
          className={`flex items-center gap-2 mt-3 pt-2.5 border-t border-border transition-opacity ${
            isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          }`}
        >
          <Link
            href={`/explain/${clause.doc_id}/${clause.clause_id}`}
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 text-[10px] font-mono text-text-muted hover:text-accent-primary transition-colors"
          >
            <Sparkles style={{ width: 10, height: 10 }} /> Explain this
          </Link>
          <span className="text-text-dim text-[10px]">·</span>
          <Link
            href={`/simulate/${clause.doc_id}?clause=${clause.clause_id}`}
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-1 text-[10px] font-mono text-text-muted hover:text-status-success transition-colors"
          >
            <FlaskConical style={{ width: 10, height: 10 }} /> Simulate impact
          </Link>
        </div>
      )}
    </motion.div>
  );
});

export default ClauseCard;
