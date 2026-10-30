"use client";

import { useEffect, useId, useState } from "react";
import { cn } from "@/lib/utils";

/** A numeric input that keeps what the person is typing until it is a valid number, then
 *  commits it. The value shown is `scale` times the stored one (a rate stored as 0.1 is
 *  typed as 10; rupees stored in rupees are typed in lakh). */
export default function NumField({
  value,
  onCommit,
  scale = 1,
  min,
  max,
  step,
  suffix,
  label,
  className,
  disabled,
  invalid,
}: {
  value: number;
  onCommit: (v: number) => void;
  scale?: number;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
  label: string;
  className?: string;
  disabled?: boolean;
  invalid?: boolean;
}) {
  const shown = (v: number) => String(Number((v * scale).toFixed(4)));
  const [text, setText] = useState(shown(value));
  const [focused, setFocused] = useState(false);
  const id = useId();

  useEffect(() => {
    if (!focused) setText(shown(value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, focused, scale]);

  const commit = (raw: string) => {
    const n = Number(raw);
    if (raw.trim() === "" || !Number.isFinite(n)) return;
    const clamped = Math.min(max ?? Infinity, Math.max(min ?? -Infinity, n));
    onCommit(clamped / scale);
  };

  return (
    <span className={cn("relative inline-flex items-center", className)}>
      <input
        id={id}
        aria-label={label}
        aria-invalid={invalid || undefined}
        inputMode="decimal"
        type="text"
        disabled={disabled}
        value={text}
        step={step}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false);
          setText(shown(value));
        }}
        onChange={(e) => {
          setText(e.target.value);
          commit(e.target.value);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowUp" || e.key === "ArrowDown") {
            e.preventDefault();
            const s = (step ?? 1) * (e.key === "ArrowUp" ? 1 : -1);
            const n = Number(text) + s;
            if (Number.isFinite(n)) {
              setText(String(Number(n.toFixed(4))));
              commit(String(n));
            }
          }
        }}
        className={cn(
          "h-8 w-full min-w-0 rounded-[4px] border bg-bg-surface px-2 text-right font-mono text-[13px] text-text-primary",
          "hover:border-glow focus:border-signal focus:outline-none disabled:opacity-50",
          suffix && "pr-7",
          invalid ? "border-status-error" : "border-border-light"
        )}
      />
      {suffix && (
        <span className="pointer-events-none absolute right-2 font-mono text-[11px] text-text-dim">{suffix}</span>
      )}
    </span>
  );
}
