"use client";
import { useCallback, useRef, useState } from "react";
import { api, Phase2UnavailableError, SIMULATE_STREAM_URL } from "@/lib/api";
import { openSSE, type SSEHandle } from "@/lib/sse";
import type {
  SimulationConfig,
  SimulationCreated,
  SimulationStep,
  PolicyVerdict,
} from "@/types";

export type SimulationPhase = "idle" | "starting" | "running" | "complete" | "offline" | "error";

export interface SimulationState {
  phase: SimulationPhase;
  created: SimulationCreated | null;
  steps: SimulationStep[];
  finalVerdict: PolicyVerdict | null;
  finalGini: number | null;
  finalCompliance: number | null;
  finalRevenue: number | null;
  effectiveRateLow: number | null;
  effectiveRateHigh: number | null;
  narrative: string | null;
  error: string | null;
}

const INITIAL: SimulationState = {
  phase: "idle",
  created: null,
  steps: [],
  finalVerdict: null,
  finalGini: null,
  finalCompliance: null,
  finalRevenue: null,
  effectiveRateLow: null,
  effectiveRateHigh: null,
  narrative: null,
  error: null,
};

/**
 * One live simulation run: POST to create → SSE stream of per-step metrics.
 * Plain useState (not the document store) so /compare can run two
 * independent instances side by side.
 */
export function useSimulation(docId: string) {
  const [state, setState] = useState<SimulationState>(INITIAL);
  const sseRef = useRef<SSEHandle | null>(null);

  const run = useCallback(
    async (config: Partial<SimulationConfig>) => {
      sseRef.current?.abort();
      setState({ ...INITIAL, phase: "starting" });

      let created: SimulationCreated;
      try {
        created = await api.createSimulation(docId, config);
      } catch (error) {
        if (error instanceof Phase2UnavailableError) {
          setState({ ...INITIAL, phase: "offline" });
        } else {
          setState({
            ...INITIAL,
            phase: "error",
            error: error instanceof Error ? error.message : String(error),
          });
        }
        return;
      }

      setState((s) => ({ ...s, phase: "running", created }));

      sseRef.current = openSSE(
        SIMULATE_STREAM_URL(docId, created.simulation_id),
        (event) => {
          if (event.stage === "sim_complete") {
            setState((s) => ({
              ...s,
              phase: "complete",
              finalVerdict: event.policy_verdict as PolicyVerdict,
              finalGini: event.final_gini,
              finalCompliance: event.final_compliance_rate,
              finalRevenue: event.final_revenue ?? null,
              effectiveRateLow: event.effective_rate_low ?? null,
              effectiveRateHigh: event.effective_rate_high ?? null,
              narrative: event.narrative ?? null,
            }));
            sseRef.current?.abort();
          } else if (event.metrics) {
            const step = event.metrics as SimulationStep;
            setState((s) => ({ ...s, steps: [...s.steps, step] }));
          }
        },
        {
          onError: () =>
            setState((s) =>
              s.phase === "complete"
                ? s
                : { ...s, phase: "error", error: "Simulation stream lost — re-run to try again." }
            ),
        }
      );
    },
    [docId]
  );

  const stop = useCallback(() => sseRef.current?.abort(), []);

  return { state, run, stop };
}
