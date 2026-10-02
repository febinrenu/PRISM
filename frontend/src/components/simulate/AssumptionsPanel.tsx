"use client";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown, Loader2, ShieldCheck } from "lucide-react";
import { api, Phase2UnavailableError } from "@/lib/api";
import { alpha, tokens } from "@/lib/tokens";
import type { SimParam } from "@/types";

const TAG_STYLE: Record<SimParam["tag"], { color: string; label: string }> = {
  sourced: { color: tokens.status.success, label: "Sourced" },
  illustrative: { color: tokens.status.warning, label: "Illustrative" },
};

function formatValue(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** "No room for doubt" transparency table — every model parameter, its value,
 *  its rationale, and whether it is survey-sourced or an illustrative choice. */
export default function AssumptionsPanel() {
  const [params, setParams] = useState<SimParam[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.getSimulationParams();
        if (!cancelled) setParams(res.params);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof Phase2UnavailableError) setError("offline");
        else setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Nothing useful to show — stay silent rather than render an error box.
  if (error || (params && params.length === 0)) return null;

  const groups = params
    ? params.reduce<Record<string, SimParam[]>>((acc, p) => {
        (acc[p.group] ??= []).push(p);
        return acc;
      }, {})
    : {};

  return (
    <div className="glass-card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-6 py-4 text-left"
      >
        <ShieldCheck className="w-4 h-4 flex-shrink-0 text-accent-primary" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-display text-text-primary">Model assumptions</p>
          <p className="text-[10px] font-mono text-text-dim mt-0.5">
            Every parameter behind the simulation, with source & rationale
          </p>
        </div>
        {!params && !error && <Loader2 className="w-4 h-4 animate-spin text-text-dim" />}
        <ChevronDown
          className="w-4 h-4 flex-shrink-0 text-text-dim transition-transform"
          style={{ transform: open ? "rotate(180deg)" : "none" }}
        />
      </button>

      {open && params && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="px-6 pb-6 space-y-6 border-t border-border pt-5"
        >
          {Object.entries(groups).map(([group, rows]) => (
            <div key={group}>
              <p className="kicker !text-[9px] mb-3">{group}</p>
              <div className="space-y-2">
                {rows.map((p) => {
                  const tag = TAG_STYLE[p.tag];
                  return (
                    <div
                      key={p.key}
                      className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 rounded-lg border border-border px-4 py-3"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-display text-text-primary">{p.label}</span>
                          <span
                            className="text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-full border flex-shrink-0"
                            style={{
                              color: tag.color,
                              borderColor: alpha(tag.color, 0.4),
                              background: alpha(tag.color, 0.1),
                            }}
                          >
                            {tag.label}
                          </span>
                        </div>
                        <p className="text-[11px] text-text-muted leading-relaxed mt-1">{p.rationale}</p>
                      </div>
                      <span className="text-xs font-mono text-accent-primary sm:text-right whitespace-nowrap">
                        {formatValue(p.value)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </motion.div>
      )}
    </div>
  );
}
