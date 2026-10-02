"use client";
import { motion } from "framer-motion";
import { tokens, alpha } from "@/lib/tokens";

interface Props {
  value: number; // 0–1
  label: string;
  size?: number;
}

/** Animated radial confidence gauge (SVG arc sweep). */
export default function ConfidenceGauge({ value, label, size = 130 }: Props) {
  const clamped = Math.max(0, Math.min(1, value));
  const radius = size / 2 - 10;
  const circumference = 2 * Math.PI * radius * 0.75; // 270° arc
  const color =
    clamped >= 0.75 ? tokens.status.success : clamped >= 0.45 ? tokens.status.warning : tokens.status.error;

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <g transform={`rotate(135 ${size / 2} ${size / 2})`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={alpha(tokens.accent.primary, 0.12)}
            strokeWidth={7}
            strokeDasharray={`${circumference} ${2 * Math.PI * radius}`}
            strokeLinecap="round"
          />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={7}
            strokeLinecap="round"
            initial={{ strokeDasharray: `0 ${2 * Math.PI * radius}` }}
            animate={{ strokeDasharray: `${circumference * clamped} ${2 * Math.PI * radius}` }}
            transition={{ duration: 1.1, ease: "easeOut" }}
          />
        </g>
        <text
          x="50%"
          y="47%"
          textAnchor="middle"
          dominantBaseline="central"
          fill={tokens.text.primary}
          style={{ fontSize: size / 4.6, fontFamily: "var(--font-playfair), serif", fontWeight: 600 }}
        >
          {Math.round(clamped * 100)}%
        </text>
        <text
          x="50%"
          y="66%"
          textAnchor="middle"
          fill={tokens.text.dim}
          style={{ fontSize: 9, fontFamily: "var(--font-mono), monospace", letterSpacing: "0.15em" }}
        >
          {label.toUpperCase()}
        </text>
      </svg>
    </div>
  );
}
