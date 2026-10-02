"use client";
import { useEffect, useState } from "react";
import { Loader2, Layers } from "lucide-react";
import { api, Phase2UnavailableError } from "@/lib/api";
import LIMEHeatmap from "./LIMEHeatmap";
import type { LIMEExplanation } from "@/types";

/**
 * Second XAI lens: transformer self-attention salience from the MiniLM encoder,
 * shown beside LIME. Reuses the LIME heatmap renderer (same token shape). Loads
 * lazily and is cached server-side, so it's cheap to keep on the page.
 *
 * Honesty label: this explains the sentence-embedding encoder, not Phi-3.5.
 */
export default function AttentionCard({
  docId,
  clauseId,
  clauseText,
}: {
  docId: string;
  clauseId: string;
  clauseText: string;
}) {
  const [data, setData] = useState<(LIMEExplanation & { explains?: string }) | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    (async () => {
      try {
        const res = await api.getAttention(docId, clauseId);
        if (!cancelled) setData(res);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Phase2UnavailableError ? "offline" : e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [docId, clauseId]);

  if (data?.not_applicable) return null;

  return (
    <div className="glass-card p-6">
      <div className="flex items-center gap-2 mb-1">
        <Layers className="w-3.5 h-3.5 text-accent-primary" />
        <span className="kicker !text-[9px]">Transformer attention</span>
        <span className="text-[10px] font-mono text-text-dim">encoder salience</span>
      </div>
      <p className="text-[10px] font-mono text-text-dim mb-4">
        Mean self-attention received per token across all heads/layers — a second lens beside LIME.
        Explains the MiniLM encoder, not the Phi-3.5 generator.
      </p>

      {!data && !error && (
        <div className="flex items-center gap-2 text-xs font-mono text-text-dim py-4">
          <Loader2 className="w-3.5 h-3.5 animate-spin" /> Reading attention…
        </div>
      )}
      {error && (
        <p className="text-xs font-mono text-status-warning py-2">
          {error === "offline" ? "Attention module offline." : error}
        </p>
      )}
      {data && data.lime_tokens.length > 0 && (
        <LIMEHeatmap clauseText={clauseText} limeTokens={data.lime_tokens} />
      )}
    </div>
  );
}
