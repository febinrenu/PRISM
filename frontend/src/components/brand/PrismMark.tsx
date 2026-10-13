import React from "react";
import { tokens } from "@/lib/tokens";

type PrismMarkProps = {
  size?: number;
  className?: string;
  /** Draw for a paper background instead of ink. */
  onPaper?: boolean;
  title?: string;
};

/**
 * The mark: a plain ray (the text of the law) enters a prism and leaves as a
 * single vermilion signal (the reading that can be checked).
 */
export default function PrismMark({ size = 32, className, onPaper = false, title = "PRISM" }: PrismMarkProps) {
  const line = onPaper ? tokens.ink[900] : tokens.paper[100];
  const out = onPaper ? tokens.signal.ink : tokens.signal[500];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={className}
      {...(title ? { role: "img", "aria-label": title } : { "aria-hidden": true })}
    >
      <path d="M16 4.5 L28.5 26.5 H3.5 Z" fill="none" stroke={line} strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M0.5 19.2 L10.4 16.4" stroke={line} strokeWidth="1.4" strokeLinecap="round" opacity="0.75" />
      <path d="M10.4 16.4 L21.2 17.6" stroke={line} strokeWidth="1" strokeLinecap="round" opacity="0.35" />
      <path d="M21.2 17.6 L31.5 22.4" stroke={out} strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

export function Wordmark({ className, onPaper = false }: { className?: string; onPaper?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className ?? ""}`}>
      <PrismMark size={26} onPaper={onPaper} title="" />
      <span className="font-sans font-semibold tracking-[0.22em] text-[13px] leading-none">PRISM</span>
    </span>
  );
}
