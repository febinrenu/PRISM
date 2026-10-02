"use client";
import { useMemo } from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { alpha, tokens } from "@/lib/tokens";
import type { LIMEToken } from "@/types";

const POSITIVE = tokens.status.success; // pushes toward "causal"
const NEGATIVE = tokens.status.error;   // pushes away

interface Props {
  clauseText: string;
  limeTokens: LIMEToken[];
}

/**
 * LIME token heatmap: the clause rendered word-by-word, each influential
 * token tinted by the sign and magnitude of its LIME weight.
 */
export default function LIMEHeatmap({ clauseText, limeTokens }: Props) {
  // Map char positions → token weight for exact-position tinting.
  const segments = useMemo(() => {
    const byPosition = limeTokens
      .filter((t) => t.position >= 0)
      .sort((a, b) => a.position - b.position);

    const out: Array<{ text: string; token?: LIMEToken }> = [];
    let cursor = 0;
    for (const token of byPosition) {
      if (token.position < cursor) continue; // overlapping occurrence
      if (token.position > cursor) {
        out.push({ text: clauseText.slice(cursor, token.position) });
      }
      out.push({
        text: clauseText.slice(token.position, token.position + token.token.length),
        token,
      });
      cursor = token.position + token.token.length;
    }
    if (cursor < clauseText.length) out.push({ text: clauseText.slice(cursor) });
    return out;
  }, [clauseText, limeTokens]);

  return (
    <TooltipProvider delayDuration={100}>
      <p className="text-sm leading-loose text-text-secondary whitespace-pre-wrap">
        {segments.map((segment, i) => {
          if (!segment.token) return <span key={i}>{segment.text}</span>;
          const { weight, normalized_weight } = segment.token;
          const color = weight >= 0 ? POSITIVE : NEGATIVE;
          return (
            <Tooltip key={i}>
              <TooltipTrigger asChild>
                <mark
                  className="rounded px-0.5 cursor-help transition-shadow hover:shadow-glow-sm"
                  style={{
                    background: alpha(color, 0.12 + 0.38 * normalized_weight),
                    color: tokens.text.primary,
                  }}
                >
                  {segment.text}
                </mark>
              </TooltipTrigger>
              <TooltipContent>
                <div className="font-mono text-[11px] space-y-0.5">
                  <p>Token: “{segment.token.token}”</p>
                  <p style={{ color }}>
                    LIME weight: {weight >= 0 ? "+" : ""}{weight.toFixed(4)}
                  </p>
                  <p className="text-text-muted">
                    {weight >= 0
                      ? "Pushes toward causal classification"
                      : "Pushes away from causal classification"}
                  </p>
                </div>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </p>
    </TooltipProvider>
  );
}
