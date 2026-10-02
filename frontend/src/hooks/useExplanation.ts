"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, EXPLAIN_STREAM_URL, Phase2UnavailableError } from "@/lib/api";
import { openSSE, type SSEHandle } from "@/lib/sse";
import type { LIMEExplanation } from "@/types";

type ExplainState =
  | { status: "loading" }
  | { status: "running"; done: number; total: number }
  | { status: "complete"; explanation: LIMEExplanation }
  | { status: "offline" }
  | { status: "error"; message: string };

/**
 * LIME explanation for one clause. Cached explanations return instantly;
 * otherwise the job's SSE stream reports per-sample progress (llm mode
 * makes ~50 Ollama calls ≈ 1–3 minutes).
 */
export function useExplanation(docId: string, clauseId: string, mode: "proxy" | "llm") {
  const [state, setState] = useState<ExplainState>({ status: "loading" });
  const sseRef = useRef<SSEHandle | null>(null);
  const [nonce, setNonce] = useState(0);

  const rerun = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    sseRef.current?.abort();

    const attachStream = () => {
      sseRef.current = openSSE(
        EXPLAIN_STREAM_URL(docId, clauseId, mode),
        (event) => {
          if (cancelled) return;
          if (event.stage === "explain_progress") {
            setState({ status: "running", done: event.done, total: event.total });
          } else if (event.stage === "explain_complete") {
            setState({ status: "complete", explanation: event as LIMEExplanation });
            sseRef.current?.abort();
          } else if (event.stage === "error") {
            setState({ status: "error", message: event.message ?? "Explanation failed" });
            sseRef.current?.abort();
          }
        },
        {
          onError: () => {
            if (!cancelled) setState({ status: "error", message: "Stream connection lost" });
          },
        }
      );
    };

    (async () => {
      try {
        const result = await api.getExplanation(docId, clauseId, mode);
        if (cancelled) return;
        if (result.status === "complete") {
          setState({ status: "complete", explanation: result });
        } else {
          setState({ status: "running", done: 0, total: result.num_samples ?? 0 });
          attachStream();
        }
      } catch (error) {
        if (cancelled) return;
        if (error instanceof Phase2UnavailableError) setState({ status: "offline" });
        else setState({ status: "error", message: error instanceof Error ? error.message : String(error) });
      }
    })();

    return () => {
      cancelled = true;
      sseRef.current?.abort();
    };
  }, [docId, clauseId, mode, nonce]);

  return { state, rerun };
}
