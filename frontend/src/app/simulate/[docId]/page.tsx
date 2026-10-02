"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowLeft, CircleOff, FlaskConical } from "lucide-react";
import { api, Phase2UnavailableError } from "@/lib/api";
import { useSimulation } from "@/hooks/useSimulation";
import SimulationControls, { type ControlValues } from "@/components/simulate/SimulationControls";
import LiveMetricCard from "@/components/simulate/LiveMetricCard";
import VerdictCard from "@/components/simulate/VerdictCard";
import ProvenancePanel from "@/components/simulate/ProvenancePanel";
import AssumptionsPanel from "@/components/simulate/AssumptionsPanel";
import {
  BurdenChart,
  ComplianceChart,
  EffectiveRateChart,
  GiniChart,
  RevenueChart,
  formatRupees,
} from "@/components/simulate/SimulationCharts";
import PrismMark from "@/components/brand/PrismMark";
import { tokens } from "@/lib/tokens";
import type { SimulationRuleInfo } from "@/types";

export default function SimulatePage({ params }: { params: { docId: string } }) {
  const { docId } = params;
  const searchParams = useSearchParams();
  const prefilterClause = searchParams.get("clause");

  const { state, run } = useSimulation(docId);
  const [availableRules, setAvailableRules] = useState<SimulationRuleInfo[] | null>(null);
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [noRules, setNoRules] = useState(false);
  const [exporting, setExporting] = useState(false);
  const exportRef = useRef<HTMLDivElement>(null);

  // Discover available rules via a lightweight GET (no throwaway run created).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const info = await api.listSimulationRules(docId);
        if (cancelled) return;
        setAvailableRules(info.rules);
        setNoRules(info.count === 0);
      } catch (error) {
        if (cancelled) return;
        if (error instanceof Phase2UnavailableError) setRulesError("offline");
        else setRulesError(error instanceof Error ? error.message : String(error));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docId]);

  const running = state.phase === "starting" || state.phase === "running";
  const latest = state.steps[state.steps.length - 1] ?? null;
  const sparkOf = useMemo(
    () => ({
      compliance: state.steps.map((s) => s.compliance_rate),
      burden_low: state.steps.map((s) => s.avg_burden_by_type.low_income),
      burden_sme: state.steps.map((s) => s.avg_burden_by_type.small_business),
      pbi: state.steps.map((s) => s.policy_burden_index),
      revenue: state.steps.map((s) => s.revenue_total ?? 0),
    }),
    [state.steps]
  );

  const handleRun = (values: ControlValues) =>
    run({
      agent_config: values.agentConfig,
      n_steps: values.nSteps,
      rule_clause_ids: values.ruleClauseIds,
      seed: 42,
      adaptive: values.adaptive,
      calibration_mode: values.calibrationMode,
    });

  const handleExport = async () => {
    if (!exportRef.current || exporting) return;
    setExporting(true);
    try {
      const { exportSimulationReport } = await import("@/lib/reportPdf");
      await exportSimulationReport(exportRef.current, docId);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="min-h-screen app-shell bg-bg-base">
      <div className="gradient-orb-1" style={{ opacity: 0.3 }} />
      <div className="gradient-orb-3" style={{ opacity: 0.25 }} />
      <div className="noise-overlay" />

      <nav className="content-layer sticky top-0 z-20 flex items-center justify-between px-6 py-3 bg-bg-deep/90 backdrop-blur-md border-b border-border">
        <div className="flex items-center gap-3">
          <Link
            href={`/analyze/${docId}`}
            className="flex items-center gap-1.5 text-xs font-mono text-text-muted hover:text-text-primary transition-colors group"
          >
            <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-0.5 transition-transform" /> Workspace
          </Link>
          <div className="w-px h-4 bg-border" />
          <PrismMark size={24} />
          <span className="font-display font-bold text-sm text-text-primary">Simulation Theater</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded text-status-success border border-status-success/35 bg-status-success/10">
            Module C · Mesa ABM
          </span>
        </div>
        {state.created && (
          <span className="text-[10px] font-mono text-text-dim">
            {state.created.rules_source === "llm" ? "LLM-extracted rules" : "rule-based fallback"} ·{" "}
            {state.created.active_rules.length} active · seed 42
          </span>
        )}
      </nav>

      <main className="content-layer max-w-7xl mx-auto px-6 py-8 space-y-6" ref={exportRef}>
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center gap-3 mb-2">
            <span className="h-px w-8 bg-accent-primary/60" />
            <span className="kicker">Socioeconomic impact</span>
          </div>
          <h1 className="font-display text-3xl md:text-4xl text-text-primary mb-1">
            Watch the law land on a synthetic society
          </h1>
          <p className="text-sm text-text-muted max-w-2xl leading-relaxed">
            Five agent populations respond to the extracted policy rules month by month —
            compliance, financial burden, and inequality unfold live as the simulation streams.
          </p>
        </motion.div>

        {rulesError === "offline" && (
          <OfflinePanel label="Simulation module offline — start the backend with Phase 2 modules enabled." />
        )}
        {rulesError && rulesError !== "offline" && <OfflinePanel label={rulesError} />}

        {!rulesError && noRules && (
          <EmptyPanel
            title="No causal rules to simulate"
            label="This document has no clauses with a parseable obligation, penalty, or threshold to model. Run the analysis (and optionally LLM extraction) first, or try a document that imposes levies, fees, or duties."
          />
        )}

        {!rulesError && !noRules && (
          <>
            {/* Zone 1 — controls */}
            <SimulationControls
              running={running}
              availableRules={availableRules}
              prefilterClauseId={prefilterClause}
              onRun={handleRun}
            />

            {state.created?.unmatched_rule_ids && state.created.unmatched_rule_ids.length > 0 && (
              <div
                className="glass-card px-5 py-4 flex items-start gap-3"
                style={{ borderColor: `${tokens.status.warning}59` }}
              >
                <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5 text-status-warning" />
                <p className="text-xs text-text-secondary leading-relaxed">
                  {state.created.unmatched_rule_ids.length} requested rule
                  {state.created.unmatched_rule_ids.length > 1 ? "s" : ""} produced no executable
                  model and {state.created.unmatched_rule_ids.length > 1 ? "were" : "was"} skipped:{" "}
                  <span className="font-mono text-text-dim">
                    {state.created.unmatched_rule_ids.join(", ")}
                  </span>
                  . The verdict below reflects only the {state.created.active_rules.length} rule
                  {state.created.active_rules.length === 1 ? "" : "s"} that could be simulated.
                </p>
              </div>
            )}

            {/* Zone 2 — live metrics */}
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
              <LiveMetricCard
                label="Compliance rate"
                value={latest ? latest.compliance_rate * 100 : null}
                format={(v) => `${v.toFixed(1)}%`}
                spark={sparkOf.compliance}
                accent={tokens.status.success}
              />
              <LiveMetricCard
                label="Gini coefficient"
                value={latest?.gini_coefficient ?? null}
                format={(v) => v.toFixed(3)}
                gradientBar
                accent={
                  latest && latest.gini_coefficient > 0.4
                    ? tokens.status.error
                    : latest && latest.gini_coefficient < 0.3
                    ? tokens.status.success
                    : tokens.status.warning
                }
              />
              <LiveMetricCard
                label="Avg burden · low income"
                value={latest?.avg_burden_by_type.low_income ?? null}
                format={formatRupees}
                spark={sparkOf.burden_low}
                accent={tokens.agent.low_income}
              />
              <LiveMetricCard
                label="Avg burden · SME"
                value={latest?.avg_burden_by_type.small_business ?? null}
                format={formatRupees}
                spark={sparkOf.burden_sme}
                accent={tokens.agent.small_business}
              />
              <LiveMetricCard
                label="Policy burden index"
                value={latest?.policy_burden_index ?? null}
                format={(v) => v.toFixed(4)}
                spark={sparkOf.pbi}
              />
              <LiveMetricCard
                label="Govt revenue"
                value={state.finalRevenue ?? latest?.revenue_total ?? null}
                format={formatRupees}
                spark={sparkOf.revenue}
                accent={tokens.accent.primary}
              />
            </div>

            {/* Zone 3 — live charts */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
              <ChartCard title="Compliance over time" subtitle="per agent type, %">
                <ComplianceChart steps={state.steps} />
              </ChartCard>
              <ChartCard title="Financial burden" subtitle="₹ per agent, log scale, every 5 steps">
                <BurdenChart steps={state.steps} />
              </ChartCard>
              <ChartCard title="Gini trajectory" subtitle="relative burden inequality">
                <GiniChart steps={state.steps} />
              </ChartCard>
              <ChartCard title="Effective tax rate" subtitle="burden ÷ gross income, by income band, %">
                <EffectiveRateChart steps={state.steps} />
              </ChartCard>
              <ChartCard title="Government revenue" subtitle="₹ cumulative · compliance vs penalty">
                <RevenueChart steps={state.steps} />
              </ChartCard>
            </div>

            {state.phase === "error" && <OfflinePanel label={state.error ?? "Simulation failed."} />}

            {state.phase === "complete" && state.finalVerdict && state.created && (
              <>
                <VerdictCard
                  verdict={state.finalVerdict}
                  steps={state.steps}
                  nRules={state.created.active_rules.length}
                  rulesSource={state.created.rules_source}
                  narrative={state.narrative}
                  effectiveRateLow={state.effectiveRateLow}
                  effectiveRateHigh={state.effectiveRateHigh}
                  exporting={exporting}
                  onExport={handleExport}
                />
                <ProvenancePanel docId={docId} simulationId={state.created.simulation_id} />
              </>
            )}

            {/* Transparency — model assumptions behind every number above. */}
            <AssumptionsPanel />
          </>
        )}
      </main>
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-baseline justify-between mb-3">
        <p className="text-xs font-display text-text-primary">{title}</p>
        <p className="text-[9px] font-mono text-text-dim">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}

function OfflinePanel({ label }: { label: string }) {
  return (
    <div className="glass-card p-10 flex flex-col items-center gap-3 text-center">
      <CircleOff className="w-6 h-6 text-text-dim" />
      <p className="text-xs font-mono text-text-muted max-w-sm leading-relaxed">{label}</p>
    </div>
  );
}

/** Calm empty-state (not a failure) — e.g. a document with no causal rules. */
function EmptyPanel({ title, label }: { title: string; label: string }) {
  return (
    <div className="glass-card p-10 flex flex-col items-center gap-3 text-center">
      <FlaskConical className="w-6 h-6 text-text-dim" />
      <p className="text-sm font-display text-text-primary">{title}</p>
      <p className="text-xs text-text-muted max-w-md leading-relaxed">{label}</p>
    </div>
  );
}
