"use client";
import { motion } from "framer-motion";
import { CircleOff, Loader2, Play, Scale } from "lucide-react";
import { useSimulation, type SimulationState } from "@/hooks/useSimulation";
import { GiniChart } from "@/components/simulate/SimulationCharts";
import { tokens, alpha } from "@/lib/tokens";
import type { PolicyVerdict } from "@/types";

const SIM_CONFIG = { n_steps: 50, seed: 42 };

const VERDICT_COLOR: Record<PolicyVerdict, string> = {
  progressive: tokens.status.success,
  neutral: tokens.status.warning,
  regressive: tokens.status.error,
};

function ProgressBar({ state, label }: { state: SimulationState; label: string }) {
  const pct = Math.min(100, Math.round((state.steps.length / SIM_CONFIG.n_steps) * 100));
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] font-mono text-text-muted truncate">{label}</span>
        <span className="text-[10px] font-mono text-accent-primary flex-shrink-0 ml-2">{pct}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-bg-elevated overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${pct}%`, background: tokens.accent.primary }}
        />
      </div>
    </div>
  );
}

function SimResultCard({
  slot,
  accent,
  name,
  state,
}: {
  slot: "A" | "B";
  accent: string;
  name: string;
  state: SimulationState;
}) {
  const verdict = state.finalVerdict;
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-6 h-6 rounded-lg flex items-center justify-center text-[10px] font-bold border flex-shrink-0"
          style={{
            color: accent,
            borderColor: alpha(accent, 0.35),
            background: alpha(accent, 0.1),
          }}
        >
          {slot}
        </span>
        <span className="text-xs font-display font-medium text-text-primary truncate">{name}</span>
        {verdict && (
          <span
            className="ml-auto text-[9px] font-mono uppercase px-2 py-0.5 rounded-full border flex-shrink-0"
            style={{
              color: VERDICT_COLOR[verdict],
              borderColor: alpha(VERDICT_COLOR[verdict], 0.4),
              background: alpha(VERDICT_COLOR[verdict], 0.1),
            }}
          >
            {verdict}
          </span>
        )}
      </div>
      <GiniChart steps={state.steps} />
      <div className="grid grid-cols-2 gap-2 mt-3">
        <div className="rounded-lg py-2 px-1 text-center bg-bg-deep/50 border border-border">
          <p className="font-display font-bold text-lg text-text-primary">
            {state.finalGini != null ? state.finalGini.toFixed(3) : "—"}
          </p>
          <p className="text-[9px] font-mono uppercase text-text-muted">Final Gini</p>
        </div>
        <div className="rounded-lg py-2 px-1 text-center bg-bg-deep/50 border border-border">
          <p className="font-display font-bold text-lg" style={{ color: tokens.status.success }}>
            {state.finalCompliance != null ? `${(state.finalCompliance * 100).toFixed(1)}%` : "—"}
          </p>
          <p className="text-[9px] font-mono uppercase text-text-muted">Compliance</p>
        </div>
      </div>
    </div>
  );
}

/** Bottom zone of the arena — runs the same 50-step, seed-42 simulation on
 *  both documents and puts the inequality trajectories side by side. */
export default function ComparativeSimPanel({
  docIdA,
  docIdB,
  nameA,
  nameB,
}: {
  docIdA: string;
  docIdB: string;
  nameA: string;
  nameB: string;
}) {
  const simA = useSimulation(docIdA);
  const simB = useSimulation(docIdB);

  const running = [simA.state, simB.state].some(
    (s) => s.phase === "starting" || s.phase === "running"
  );
  const offline = simA.state.phase === "offline" || simB.state.phase === "offline";
  const failed = simA.state.phase === "error" || simB.state.phase === "error";
  const bothComplete = simA.state.phase === "complete" && simB.state.phase === "complete";
  const started = simA.state.phase !== "idle" || simB.state.phase !== "idle";

  const handleRun = () => {
    simA.run(SIM_CONFIG);
    simB.run(SIM_CONFIG);
  };

  let takeaway: string | null = null;
  if (bothComplete && simA.state.finalGini != null && simB.state.finalGini != null) {
    const gA = simA.state.finalGini;
    const gB = simB.state.finalGini;
    const delta = gB - gA;
    takeaway =
      Math.abs(delta) < 0.005
        ? `Both versions land at near-identical inequality (Gini ${gA.toFixed(3)} vs ${gB.toFixed(3)}).`
        : delta > 0
        ? `Document B produces higher burden inequality than A (Gini ${gB.toFixed(3)} vs ${gA.toFixed(3)}, +${delta.toFixed(3)}).`
        : `Document B distributes burden more equally than A (Gini ${gB.toFixed(3)} vs ${gA.toFixed(3)}, ${delta.toFixed(3)}).`;
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4"
    >
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <span className="h-px w-8 bg-accent-primary/60" />
            <span className="kicker">Comparative simulation</span>
          </div>
          <h2 className="font-display text-2xl text-text-primary">
            Same society, two versions of the law
          </h2>
          <p className="text-xs text-text-muted mt-1">
            Identical agent population, 50 steps, seed 42 — only the policy rules differ.
          </p>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold transition-all disabled:opacity-40 bg-accent-primary/15 border border-accent-primary/35 text-accent-primary hover:bg-accent-primary/25"
        >
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {running ? "Simulating…" : started ? "Re-run comparative simulation" : "Run comparative simulation"}
        </button>
      </div>

      {offline && (
        <div className="glass-card p-8 flex flex-col items-center gap-2 text-center">
          <CircleOff className="w-5 h-5 text-text-dim" />
          <p className="text-xs font-mono text-text-muted">
            Simulation module offline — start the backend with Phase 2 modules enabled.
          </p>
        </div>
      )}

      {failed && !offline && (
        <div className="glass-card p-6 text-center">
          <p className="text-xs font-mono text-status-error">
            {simA.state.error ?? simB.state.error ?? "Simulation failed — re-run to try again."}
          </p>
        </div>
      )}

      {running && (
        <div className="glass-card p-5 flex items-center gap-8">
          <ProgressBar state={simA.state} label={`A · ${nameA}`} />
          <ProgressBar state={simB.state} label={`B · ${nameB}`} />
        </div>
      )}

      {started && !offline && !failed && (simA.state.steps.length > 0 || simB.state.steps.length > 0) && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SimResultCard slot="A" accent={tokens.diff.removed} name={nameA} state={simA.state} />
            <SimResultCard slot="B" accent={tokens.diff.added} name={nameB} state={simB.state} />
          </div>

          {takeaway && (
            <div className="glass-card px-5 py-4 flex items-center gap-3">
              <Scale className="w-4 h-4 flex-shrink-0 text-accent-primary" />
              <p className="text-sm text-text-secondary">{takeaway}</p>
            </div>
          )}
        </>
      )}
    </motion.section>
  );
}
