"use client";
import { useEffect } from "react";
import { animate, motion, useMotionValue, useTransform } from "framer-motion";
import { alpha, tokens } from "@/lib/tokens";

interface Props {
  label: string;
  value: number | null;
  format: (v: number) => string;
  spark?: number[];
  accent?: string;
  /** for the Gini gradient bar */
  gradientBar?: boolean;
}

/** Animated SSE-driven metric card: number counts toward each new value. */
export default function LiveMetricCard({ label, value, format, spark, accent, gradientBar }: Props) {
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => format(v));

  useEffect(() => {
    if (value == null) return;
    const controls = animate(mv, value, { duration: 0.45, ease: "easeOut" });
    return controls.stop;
  }, [value, mv]);

  const color = accent ?? tokens.accent.primary;

  return (
    <div className="glass-card p-4 flex flex-col gap-2 min-w-0">
      <span className="kicker !text-[9px] truncate">{label}</span>
      <motion.span className="font-display text-2xl leading-none truncate" style={{ color }}>
        {value == null ? "—" : text}
      </motion.span>

      {gradientBar && value != null && (
        <div className="relative h-1.5 rounded-full overflow-hidden" style={{
          background: `linear-gradient(90deg, ${tokens.status.success}, ${tokens.status.warning}, ${tokens.status.error})`,
        }}>
          <motion.div
            className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full border-2"
            style={{ borderColor: tokens.text.primary, background: tokens.bg.base }}
            animate={{ left: `calc(${Math.min(value, 1) * 100}% - 5px)` }}
            transition={{ duration: 0.45 }}
          />
        </div>
      )}

      {spark && spark.length > 1 && !gradientBar && (
        <svg viewBox="0 0 100 24" className="w-full h-6" preserveAspectRatio="none">
          <polyline
            points={sparkPoints(spark)}
            fill="none"
            stroke={alpha(color, 0.8)}
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
      )}
    </div>
  );
}

function sparkPoints(values: number[]): string {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((v, i) => `${(i / (values.length - 1)) * 100},${22 - ((v - min) / span) * 20}`)
    .join(" ");
}
