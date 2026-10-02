"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { BrainCircuit, Loader2, RefreshCw, Sparkles, Table2 } from "lucide-react";
import { api, DEEP_REASONING_STREAM_URL, Phase2UnavailableError } from "@/lib/api";
import { openSSE, type SSEHandle } from "@/lib/sse";
import { tokens } from "@/lib/tokens";
import type { DeepReasoning } from "@/types";

type DeepState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "running"; message: string }
  | { status: "complete"; reasoning: string; model?: string; cached?: boolean; elapsedMs?: number }
  | { status: "not_applicable" }
  | { status: "offline" }
  | { status: "error"; message: string };

/** Split a multi-paragraph prose rationale into paragraphs on blank lines. */
function toParagraphs(text: string): string[] {
  return text
    .split(/\n\s*\n/)
    .map((p) => p.replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

/**
 * On-demand deep reasoning for a clause. The one-line model rationale lives in
 * LLMExtractionCard; this is its richer, expandable companion. Fetches the
 * deep-reasoning endpoint on click: a 200 renders instantly (including cached
 * results), a 202 opens the SSE stream and shows live progress until
 * `deep_complete`.
 */
export default function DeepReasoningCard({
  docId,
  clauseId,
}: {
  docId: string;
  clauseId: string;
}) {
  const [state, setState] = useState<DeepState>({ status: "idle" });
  const sseRef = useRef<SSEHandle | null>(null);
  // Bumped on unmount and on each new request so stale async resolutions are ignored.
  const genRef = useRef(0);

  // Reset when navigating to another clause; tear down any live stream.
  useEffect(() => {
    setState({ status: "idle" });
    return () => {
      genRef.current += 1;
      sseRef.current?.abort();
    };
  }, [docId, clauseId]);

  const generate = useCallback(
    (force = false) => {
      sseRef.current?.abort();
      const gen = ++genRef.current;
      const cancelled = () => genRef.current !== gen;
      setState({ status: "loading" });

      const attachStream = () => {
        sseRef.current = openSSE(
          DEEP_REASONING_STREAM_URL(docId, clauseId, force),
          (event) => {
            if (cancelled()) return;
            if (event.stage === "deep_progress") {
              setState({ status: "running", message: event.message ?? "Reasoning…" });
            } else if (event.stage === "deep_complete") {
              setState({
                status: "complete",
                reasoning: event.reasoning ?? "",
                model: event.model,
                cached: event.cached,
                elapsedMs: event.generation_time_ms,
              });
              sseRef.current?.abort();
            } else if (event.stage === "error") {
              setState({ status: "error", message: event.message ?? "Reasoning failed" });
              sseRef.current?.abort();
            }
          },
          {
            onError: () => {
              if (!cancelled()) setState({ status: "error", message: "Stream connection lost" });
            },
          }
        );
      };

      (async () => {
        try {
          const result = await api.getDeepReasoning(docId, clauseId, force);
          if (cancelled()) return;
          if (result.not_applicable === "table") {
            setState({ status: "not_applicable" });
            return;
          }
          if (result.status === "running") {
            setState({ status: "running", message: "Generating deep explanation…" });
            attachStream();
          } else {
            setState({
              status: "complete",
              reasoning: result.reasoning ?? "",
              model: result.model,
              cached: result.cached,
              elapsedMs: result.generation_time_ms,
            });
          }
        } catch (error) {
          if (cancelled()) return;
          if (error instanceof Phase2UnavailableError) setState({ status: "offline" });
          else setState({ status: "error", message: error instanceof Error ? error.message : String(error) });
        }
      })();
    },
    [docId, clauseId]
  );

  return (
    <div className="glass-card p-6 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <BrainCircuit className="w-4 h-4 text-accent-primary" />
          <div>
            <p className="text-sm font-display text-text-primary">Deep reasoning</p>
            <p className="text-[10px] font-mono text-text-dim mt-0.5">
              A fuller, multi-paragraph rationale generated on demand
            </p>
          </div>
        </div>
        {state.status === "complete" && (
          <span className="text-[10px] font-mono text-text-dim flex items-center gap-2 whitespace-nowrap">
            {state.model && <span>{state.model}</span>}
            {state.cached
              ? <span className="px-1.5 py-0.5 rounded border border-border text-text-muted">cached</span>
              : typeof state.elapsedMs === "number" && <span>{Math.round(state.elapsedMs / 1000)}s</span>}
          </span>
        )}
      </div>

      {state.status === "idle" && (
        <button
          onClick={() => generate(false)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-mono font-semibold uppercase tracking-wider bg-accent-primary/10 border border-accent-primary/40 text-accent-primary hover:bg-accent-primary/20 transition-colors"
        >
          <Sparkles className="w-3.5 h-3.5" /> Explain in depth
        </button>
      )}

      {(state.status === "loading" || state.status === "running") && (
        <div className="flex items-center gap-3 py-4">
          <Loader2 className="w-4 h-4 text-accent-primary animate-spin flex-shrink-0" />
          <p className="text-xs font-mono text-text-muted leading-relaxed">
            {state.status === "running" ? state.message : "Requesting deep explanation…"}
          </p>
        </div>
      )}

      {state.status === "not_applicable" && (
        <div className="flex items-center gap-2.5 py-3 text-text-muted">
          <Table2 className="w-4 h-4 flex-shrink-0" />
          <p className="text-xs leading-relaxed">
            Tabular data — deep reasoning applies to prose clauses only.
          </p>
        </div>
      )}

      {state.status === "offline" && (
        <p className="text-xs font-mono text-text-muted py-2">
          Reasoning module offline — start the backend with Phase 2 enabled.
        </p>
      )}

      {state.status === "error" && (
        <div className="space-y-3 py-1">
          <p className="text-xs font-mono text-status-error leading-relaxed">{state.message}</p>
          <button
            onClick={() => generate(false)}
            className="flex items-center gap-1.5 text-[10px] font-mono text-text-muted hover:text-accent-primary transition-colors"
          >
            <RefreshCw className="w-3 h-3" /> Retry
          </button>
        </div>
      )}

      {state.status === "complete" && (
        <div className="space-y-3">
          {toParagraphs(state.reasoning).length > 0 ? (
            <div className="space-y-3">
              {toParagraphs(state.reasoning).map((para, i) => (
                <p key={i} className="text-sm text-text-secondary leading-relaxed">
                  {para}
                </p>
              ))}
            </div>
          ) : (
            <p className="text-xs font-mono text-text-muted">The model returned no reasoning.</p>
          )}
          <button
            onClick={() => generate(true)}
            className="flex items-center gap-1.5 text-[10px] font-mono text-text-dim hover:text-accent-primary transition-colors"
            style={{ color: tokens.text.dim }}
            title="Discard the cached rationale and generate a fresh one"
          >
            <RefreshCw className="w-3 h-3" /> Regenerate
          </button>
        </div>
      )}
    </div>
  );
}
