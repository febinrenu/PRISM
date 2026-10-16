"use client";

import { Contrast } from "lucide-react";
import { useTheme } from "@/design/theme";
import { cn } from "@/lib/utils";

/** Paper or ink for the app; the landing story stays ink either way. */
export default function ThemeToggle({ className, withLabel }: { className?: string; withLabel?: boolean }) {
  const [theme, setTheme] = useTheme();
  const next = theme === "light" ? "dark" : "light";
  return (
    <button
      type="button"
      onClick={() => setTheme(next)}
      aria-pressed={theme === "light"}
      aria-label={withLabel ? undefined : `Switch to the ${next} theme`}
      title={`Switch to the ${next} theme`}
      className={cn(
        "inline-flex h-9 items-center justify-center gap-2 rounded-[4px] border border-border text-text-secondary transition-colors hover:border-border-light hover:text-text-primary",
        withLabel ? "px-3 text-[14px]" : "w-9",
        className
      )}
    >
      <Contrast className="h-4 w-4" aria-hidden />
      {withLabel ? <span>{theme === "light" ? "Dark theme" : "Light theme"}</span> : null}
    </button>
  );
}
