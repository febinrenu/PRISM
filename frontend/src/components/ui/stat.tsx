import * as React from "react";
import { cn } from "@/lib/utils";

type StatProps = React.HTMLAttributes<HTMLDivElement> & {
  label: string;
  value: React.ReactNode;
  accent?: boolean;
};

/** Editorial stat: oversized Playfair number over a mono kicker label. */
export function Stat({ label, value, accent = false, className, ...props }: StatProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)} {...props}>
      <span
        className={cn(
          "font-display text-3xl leading-none",
          accent ? "text-accent-primary" : "text-text-primary"
        )}
      >
        {value}
      </span>
      <span className="kicker">{label}</span>
    </div>
  );
}
