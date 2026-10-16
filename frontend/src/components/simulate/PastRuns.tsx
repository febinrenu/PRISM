"use client";

import { useEffect, useState } from "react";
import { History } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { SimulationRunSummary } from "@/types";

const VERDICT_TONE: Record<string, string> = {
  progressive: "text-status-success",
  neutral: "text-text-secondary",
  regressive: "text-status-warning",
};

/**
 * Every saved sandbox run for this document, newest first. Opening one shows
 * it exactly as it finished; `refresh` changes after each new run.
 */
export default function PastRuns({
  docId,
  current,
  refresh,
  onOpen,
}: {
  docId: string;
  current: string | null;
  refresh: unknown;
  onOpen: (simulationId: string) => void;
}) {
  const [runs, setRuns] = useState<SimulationRunSummary[] | null>(null);
  useEffect(() => {
    let live = true;
    api
      .listSimulationRuns(docId)
      .then((r) => live && setRuns(r.runs))
      .catch(() => live && setRuns([]));
    return () => {
      live = false;
    };
  }, [docId, refresh]);

  if (!runs || runs.length === 0) return null;
  return (
    <section aria-labelledby="past-runs-h" className="glass-card p-5">
      <div className="mb-3 flex items-center gap-2">
        <History className="h-4 w-4 text-text-dim" aria-hidden />
        <h3 id="past-runs-h" className="text-[14px] text-text-primary">
          Past runs
        </h3>
        <span className="font-mono text-micro text-text-dim">{runs.length}</span>
      </div>
      <ul className="divide-y divide-border">
        {runs.map((r) => (
          <li key={r.simulation_id}>
            <button
              type="button"
              onClick={() => onOpen(r.simulation_id)}
              aria-current={current === r.simulation_id ? "true" : undefined}
              className={cn(
                "grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-0.5 py-2.5 text-left transition-colors hover:bg-bg-elevated sm:grid-cols-[10rem_1fr_auto]",
                current === r.simulation_id && "bg-signal/[0.06]"
              )}
            >
              <span className="font-mono text-[12px] text-text-muted">
                {new Date(r.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
              </span>
              <span className="text-[13px] text-text-secondary max-sm:col-span-2 max-sm:row-start-2">
                {r.n_agents.toLocaleString("en-IN")} agents · {r.n_steps} steps · {r.n_rules} {r.rules_source === "llm" ? "model" : "rule-based"} rule
                {r.n_rules === 1 ? "" : "s"}
                {r.adaptive ? " · adaptive" : ""}
              </span>
              <span className={cn("text-right font-mono text-[12px]", VERDICT_TONE[r.policy_verdict])}>
                {r.policy_verdict} · Gini {r.final_gini.toFixed(3)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
