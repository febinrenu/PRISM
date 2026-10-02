"use client";
import { useCallback, useEffect, useRef } from "react";
import { useDocumentStore } from "./useDocumentStore";
import { api, LLM_STREAM_URL, Phase2UnavailableError } from "@/lib/api";
import { openSSE, type SSEHandle } from "@/lib/sse";
import type { LLMStreamEvent } from "@/types";

/**
 * Phase 2 LLM extraction: hydrates cached extractions on mount, and exposes
 * start() to launch/attach to the extraction stream. The backend job
 * survives disconnects, replays history on re-attach, and caches per-clause
 * results on disk — start() is always safe to call.
 */
export function useLLMExtraction(docId: string | null) {
  const sseRef = useRef<SSEHandle | null>(null);
  const { setLLMStage, setLLMProgress, setLLMSummary } = useDocumentStore();

  // Hydrate cached extractions (previous run / previous server session).
  useEffect(() => {
    if (!docId) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await api.getLLMExtractions(docId);
        if (cancelled) return;
        const store = useDocumentStore.getState();
        for (const item of data.extractions) {
          store.mergeLLMExtraction(item.clause_id, item.extraction, item.extraction_method);
        }
        if (data.summary) store.setLLMSummary(data.summary);
        if (data.status === "complete") store.setLLMStage("complete");
        else if (data.status === "running") start(); // re-attach to a live job
      } catch (error) {
        if (error instanceof Phase2UnavailableError) return; // module offline — banner hides
      }
    })();
    return () => {
      cancelled = true;
      sseRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docId]);

  const start = useCallback(
    (scope: "auto" | "all" = "auto") => {
      if (!docId) return;
      const state = useDocumentStore.getState();
      if (state.llmStage === "running") return;

      sseRef.current?.abort();
      setLLMStage("running");

      sseRef.current = openSSE(
        LLM_STREAM_URL(docId, scope),
        (raw) => {
          const event = raw as LLMStreamEvent;
          const store = useDocumentStore.getState();
          switch (event.stage) {
            case "llm_started":
              store.setLLMProgress(0, event.selected);
              break;
            case "llm_clause":
              if (event.status === "done") {
                store.mergeLLMExtraction(event.clause_id, event.extraction, event.extraction_method);
                store.setLLMProgress(event.current, event.total);
              } else if (event.status === "error") {
                store.setLLMProgress(event.current, event.total);
              }
              break;
            case "llm_complete":
              store.setLLMSummary(event.summary);
              store.setLLMStage("complete");
              sseRef.current?.abort();
              break;
            case "error":
              store.setLLMStage("error");
              sseRef.current?.abort();
              break;
          }
        },
        {
          method: "POST",
          onError: () => setLLMStage("error"),
        }
      );
    },
    [docId, setLLMStage]
  );

  return { start };
}
