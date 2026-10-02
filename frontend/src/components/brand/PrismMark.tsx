import React from "react";
import { tokens } from "@/lib/tokens";

type PrismMarkProps = {
  size?: number;
  className?: string;
};

export default function PrismMark({ size = 32, className }: PrismMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 56 56"
      role="img"
      aria-label="PRISM logo"
      className={className}
    >
      <defs>
        <linearGradient id="prism-top" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={tokens.accent.bright} />
          <stop offset="100%" stopColor={tokens.accent.primary} />
        </linearGradient>
        <linearGradient id="prism-left" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={tokens.accent.primary} />
          <stop offset="100%" stopColor={tokens.accent.secondary} />
        </linearGradient>
        <linearGradient id="prism-right" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={tokens.entity.BENEFICIARY.text} />
          <stop offset="100%" stopColor={tokens.entity.BENEFICIARY.base} />
        </linearGradient>
      </defs>

      <rect x="2" y="2" width="52" height="52" rx="13" fill={tokens.bg.elevated} stroke={tokens.border.DEFAULT} />
      <polygon points="28,10 42,20 28,28 14,20" fill="url(#prism-top)" />
      <polygon points="14,20 28,28 28,46 14,34" fill="url(#prism-left)" />
      <polygon points="42,20 28,28 28,46 42,34" fill="url(#prism-right)" />
      <polyline points="28,10 42,20 42,34 28,46 14,34 14,20 28,10" fill="none" stroke="rgba(255,255,255,0.28)" strokeWidth="1" />
    </svg>
  );
}
