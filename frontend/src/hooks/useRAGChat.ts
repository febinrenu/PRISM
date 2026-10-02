"use client";

import { useCallback, useRef, useState } from "react";
import { openSSE, type SSEHandle } from "@/lib/sse";
import { RAG_STREAM_URL } from "@/lib/api";
import type { ChatMessage, RAGStreamEvent } from "@/types";

/** Drives the RAG chat: sends a question, streams the cited answer token by
 *  token, and appends citations + confidence when the stream completes. */
export function useRAGChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const handleRef = useRef<SSEHandle | null>(null);

  const send = useCallback(
    (question: string, docIds: string[], strict: boolean) => {
      const q = question.trim();
      if (!q || busy) return;

      setMessages((prev) => [
        ...prev,
        { role: "user", content: q },
        { role: "assistant", content: "", streaming: true },
      ]);
      setBusy(true);

      const patchAssistant = (patch: Partial<ChatMessage>) =>
        setMessages((prev) => {
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].role === "assistant") {
              next[i] = { ...next[i], ...patch };
              break;
            }
          }
          return next;
        });

      const appendToken = (token: string) =>
        setMessages((prev) => {
          const next = [...prev];
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].role === "assistant") {
              next[i] = { ...next[i], content: next[i].content + token };
              break;
            }
          }
          return next;
        });

      handleRef.current = openSSE(
        RAG_STREAM_URL(q, docIds, strict),
        (data: RAGStreamEvent) => {
          if (data.stage === "retrieval") {
            patchAssistant({
              citations: data.citations,
              retrievalConfidence: data.retrieval_confidence,
            });
          } else if (data.stage === "token") {
            appendToken(data.token);
          } else if (data.stage === "done") {
            patchAssistant({ streaming: false, grounded: data.grounded });
            setBusy(false);
          } else if (data.stage === "error") {
            patchAssistant({ streaming: false, error: data.message });
            setBusy(false);
          }
        },
        {
          onError: (err) => {
            patchAssistant({ streaming: false, error: err.message });
            setBusy(false);
          },
          onClose: () => setBusy(false),
        }
      );
    },
    [busy]
  );

  const stop = useCallback(() => {
    handleRef.current?.abort();
    setBusy(false);
    setMessages((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].role === "assistant") {
          next[i] = { ...next[i], streaming: false };
          break;
        }
      }
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    handleRef.current?.abort();
    setMessages([]);
    setBusy(false);
  }, []);

  return { messages, busy, send, stop, reset };
}
