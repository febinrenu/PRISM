"use client";
import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

/**
 * Inline text with an expand/collapse toggle — replaces hard truncation so the
 * full text is always reachable. Short strings render as-is with no control.
 * Mirrors the SpanBlock more/less pattern used in the Causal analytics tab.
 */
export default function ExpandableText({
  text,
  max = 140,
  className,
  accentColor,
}: {
  text: string;
  max?: number;
  className?: string;
  accentColor?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const clean = (text ?? "").trim();

  if (clean.length <= max) {
    return <span className={className}>{clean || "—"}</span>;
  }

  // Cut on a word boundary so the preview never splits a token.
  const cut = clean.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  const short = (lastSpace > max * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd();

  return (
    <span className={className}>
      {expanded ? clean : `${short}… `}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setExpanded((x) => !x);
        }}
        className="inline-flex items-center gap-0.5 text-[9px] font-mono uppercase tracking-wider align-baseline transition-opacity opacity-70 hover:opacity-100"
        style={accentColor ? { color: accentColor } : undefined}
      >
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {expanded ? "less" : "more"}
      </button>
    </span>
  );
}
