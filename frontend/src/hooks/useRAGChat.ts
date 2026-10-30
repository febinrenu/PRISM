"use client";

import { useCallback, useRef, useState } from "react";
import { openSSE, type SSEHandle } from "@/lib/sse";
import { RAG_STREAM_POST_URL } from "@/lib/api";
import type { ChatMessage, RAGStreamEvent } from "@/types";

/** Turns of conversation sent with a question so a follow-up ("and for senior
 *  citizens?") is understood; the server keeps nothing between questions. */
const HISTORY_TURNS = 4;

/** Drives the RAG chat: sends a question with the earlier turns, streams the
 *  cited answer token by token, and fills in the plan, the sources and the
 *  verification verdict as they arrive. */
export function useRAGChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const handleRef = useRef<SSEHandle | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);
  messagesRef.current = messages;

  const patchAssistant = useCallback((fn: (m: ChatMessage) => Partial<ChatMessage>) => {
    setMessages((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].role === "assistant") {
          next[i] = { ...next[i], ...fn(next[i]) };
          break;
        }
      }
      return next;
    });
  }, []);

  const send = useCallback(
    (question: string, docIds: string[], strict: boolean) => {
      const q = question.trim();
      if (!q || busy) return;

      // earlier turns that produced an answer; an errored or unfinished one says nothing
      const history = messagesRef.current
        .filter((m) => m.content && !m.error && !m.streaming)
        .slice(-2 * HISTORY_TURNS)
        .map((m) => ({ role: m.role, content: m.content.slice(0, 600) }));

      setMessages((prev) => [
        ...prev,
        { role: "user", content: q },
        { role: "assistant", content: "", streaming: true },
      ]);
      setBusy(true);

      handleRef.current = openSSE(
        RAG_STREAM_POST_URL,
        (data: RAGStreamEvent) => {
          switch (data.stage) {
            case "plan":
              patchAssistant(() => ({
                plan: {
                  question: data.question, standalone: data.standalone, intent: data.intent,
                  sections: data.sections, acts: data.acts,
                },
              }));
              break;
            case "retrieval":
              patchAssistant(() => ({
                citations: data.citations,
                retrievalConfidence: data.retrieval_confidence,
                exactMatch: !!data.exact_match,
                gated: !!data.gated,
              }));
              break;
            case "token":
              patchAssistant((m) => ({ content: m.content + data.token }));
              break;
            case "revising":
              patchAssistant(() => ({ revising: data.reason }));
              break;
            case "replace":
              patchAssistant(() => ({ content: data.answer, revised: true, revising: undefined }));
              break;
            case "warning":
              patchAssistant(() => ({ warning: data.message }));
              break;
            case "done":
              patchAssistant(() => ({
                streaming: false,
                revising: undefined,
                content: data.answer,
                verdict: {
                  state: data.state, grounded: data.grounded, abstained: data.abstained,
                  cited_sources: data.cited_sources, invalid_citations: data.invalid_citations,
                  unsupported_numbers: data.unsupported_numbers, claims: data.claims,
                  n_supported: data.n_supported, n_claims: data.n_claims,
                  n_uncited: data.n_uncited, n_conflicts: data.n_conflicts,
                },
                retrievalConfidence: data.retrieval_confidence,
                exactMatch: !!data.exact_match,
                backendUsed: data.backend_used ?? null,
                latencyMs: data.latency_ms,
                revised: !!data.revised,
              }));
              setBusy(false);
              break;
            case "error":
              patchAssistant(() => ({ streaming: false, revising: undefined, error: data.message }));
              setBusy(false);
              break;
          }
        },
        {
          method: "POST",
          body: { question: q, doc_ids: docIds, strict, history },
          onError: (err) => {
            patchAssistant(() => ({ streaming: false, revising: undefined, error: err.message }));
            setBusy(false);
          },
          onClose: () => setBusy(false),
        }
      );
    },
    [busy, patchAssistant]
  );

  const stop = useCallback(() => {
    handleRef.current?.abort();
    setBusy(false);
    patchAssistant(() => ({ streaming: false, revising: undefined }));
  }, [patchAssistant]);

  const reset = useCallback(() => {
    handleRef.current?.abort();
    setMessages([]);
    setBusy(false);
  }, []);

  return { messages, busy, send, stop, reset };
}
