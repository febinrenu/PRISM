"use client";
import { useEffect, useRef } from "react";
import { useDocumentStore } from "./useDocumentStore";
import { api, SSE_URL } from "@/lib/api";
import { openSSE, type SSEHandle } from "@/lib/sse";
import type { Clause, SSEEvent } from "@/types";

/**
 * Analysis session with hydration:
 *  - already-analyzed document → hydrate instantly from REST (no overlay,
 *    no SSE, no accidental re-analysis)
 *  - fresh document → live SSE pipeline stream
 *  - dropped SSE connection → re-probe; hydrate if the run finished
 *    server-side, otherwise reconnect (backend replays completed runs;
 *    the store dedupes clauses by clause_id)
 *
 * Clause additions are batched so 1,800+ SSE events don't cause 1,800+
 * React re-renders.
 */
const FLUSH_INTERVAL = 120; // ms between batched clause flushes
const MAX_RECONNECTS = 2;

export function useAnalysisSession(docId: string | null) {
  const sseRef = useRef<SSEHandle | null>(null);
  const bufRef = useRef<Clause[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectsRef = useRef(0);
  const disposedRef = useRef(false);

  const { setStage, setProcessedCount, setStats } = useDocumentStore();

  useEffect(() => {
    if (!docId) return;
    disposedRef.current = false;
    reconnectsRef.current = 0;

    // Direct navigation / switching documents: make sure the store belongs
    // to THIS doc (setDocId resets all state when the id changes).
    const store = useDocumentStore.getState();
    if (store.docId !== docId) {
      store.setDocId(docId, "", 0);
    }

    const flushBuffer = () => {
      if (bufRef.current.length === 0) return;
      const buf = bufRef.current;
      bufRef.current = [];
      useDocumentStore.getState().addClauses(buf);
    };

    timerRef.current = setInterval(flushBuffer, FLUSH_INTERVAL);

    const hydrateFromRest = async (): Promise<boolean> => {
      try {
        const stats = await api.getStats(docId);
        const { clauses } = await api.getClauses(docId);
        if (disposedRef.current) return true;
        useDocumentStore.getState().hydrate(clauses, stats);
        return true;
      } catch {
        return false; // 404 → not analyzed yet
      }
    };

    const handleEvent = (raw: any) => {
      if (!raw || raw.stage === "heartbeat") return;
      const data = raw as SSEEvent;

      switch (data.stage) {
        case "parsing":
          setStage("parsing", data.message || "Parsing PDF…", data.progress ?? 0);
          break;
        case "segmentation":
          setStage("segmentation", data.message || "Segmenting clauses…", data.progress ?? 0);
          if (data.total) setProcessedCount(0, data.total);
          break;
        case "ner":
          if (data.clause) bufRef.current.push(data.clause);
          setStage("ner", data.message || "Extracting entities…", data.progress ?? 0);
          if (data.current && data.total) setProcessedCount(data.current, data.total);
          break;
        case "embeddings_update":
          flushBuffer();
          if (data.updates?.length) {
            useDocumentStore.getState().updateClauseEmbeddings(data.updates);
          }
          break;
        case "embedding":
          flushBuffer();
          setStage("embedding", data.message || "Generating embeddings…", data.progress ?? 0);
          break;
        case "graph":
          setStage("graph", data.message || "Building knowledge graph…", 80);
          break;
        case "complete":
          flushBuffer();
          setStage("complete", "Analysis complete", 100);
          if (data.stats) setStats(data.stats);
          sseRef.current?.abort();
          break;
        case "error":
          setStage("error", data.message || "Analysis failed");
          sseRef.current?.abort();
          break;
        default:
          break;
      }
    };

    const connect = () => {
      if (disposedRef.current) return;
      sseRef.current = openSSE(SSE_URL(docId), handleEvent, {
        onError: async () => {
          if (disposedRef.current) return;
          flushBuffer();
          const state = useDocumentStore.getState();
          if (state.stage === "complete" || state.stage === "error") return;

          // Did the run finish server-side while we were disconnected?
          if (await hydrateFromRest()) return;

          if (reconnectsRef.current < MAX_RECONNECTS) {
            reconnectsRef.current += 1;
            setStage("parsing", "Connection lost — reconnecting…", 0);
            setTimeout(connect, 2000);
          } else {
            setStage("error", "Connection lost. Is the backend running?");
          }
        },
      });
    };

    (async () => {
      // Hydration probe: skip SSE entirely for already-analyzed documents.
      if (await hydrateFromRest()) return;
      if (disposedRef.current) return;
      setStage("parsing", "Contacting analysis engine…", 0);
      connect();
    })();

    return () => {
      disposedRef.current = true;
      sseRef.current?.abort();
      if (timerRef.current) clearInterval(timerRef.current);
      bufRef.current = [];
    };
  }, [docId, setStage, setProcessedCount, setStats]);
}
