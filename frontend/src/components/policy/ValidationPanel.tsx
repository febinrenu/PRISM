"use client";

import { useEffect, useState } from "react";
import { ChevronDown, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Tag } from "@/components/ui/kit";
import { crore, pct } from "@/components/policy/format";
import type { PolicyValidation } from "@/types";

/** The model against published numbers, computed on demand from the repository's code and
 *  data. The unflattering rows are shown with the caveat that explains them. */
export default function ValidationPanel() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<PolicyValidation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || data) return;
    let cancelled = false;
    api
      .policyValidation()
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Could not compute the validation."));
    return () => {
      cancelled = true;
    };
  }, [open, data]);

  return (
    <div className="glass-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left"
      >
        <div>
          <div className="kicker mb-1">How far to trust it</div>
          <p className="text-[15px] text-text-primary">The model against published tax statistics and Budget speeches</p>
        </div>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-text-muted transition-transform", open && "rotate-180")} aria-hidden />
      </button>

      {open && (
        <div className="space-y-6 border-t border-border px-5 py-5">
          {!data && !error && (
            <p className="flex items-center gap-2 text-[13px] text-text-muted">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Computing from the repository’s data…
            </p>
          )}
          {error && <p role="alert" className="text-[13px] text-status-error">{error}</p>}
          {data && (
            <>
              <section>
                <h3 className="mb-1 text-[14px] text-text-primary">Does it reproduce the tax actually paid?</h3>
                <p className="mb-3 text-[12.5px] leading-relaxed text-text-muted">{data.reading[0]}</p>
                <table className="w-full min-w-[440px] text-[13px]">
                  <thead>
                    <tr className="text-left font-mono text-micro uppercase tracking-wider text-text-dim">
                      <th className="pb-2 pr-3 font-normal">Assessment year</th>
                      <th className="pb-2 pr-3 text-right font-normal">Simulated</th>
                      <th className="pb-2 pr-3 text-right font-normal">Reported</th>
                      <th className="pb-2 text-right font-normal">Simulated ÷ reported</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.in_sample.map((r) => (
                      <tr key={r.ay} className="border-t border-border">
                        <td className="py-1.5 pr-3 font-mono text-text-secondary">{r.ay}</td>
                        <td className="py-1.5 pr-3 text-right font-mono">{crore(r.simulated_crore)}</td>
                        <td className="py-1.5 pr-3 text-right font-mono text-text-muted">{crore(r.reported_crore)}</td>
                        <td className="py-1.5 text-right font-mono">{r.ratio.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>

              <section>
                <h3 className="mb-1 text-[14px] text-text-primary">Does it forecast a year it has not seen?</h3>
                <p className="mb-3 text-[12.5px] leading-relaxed text-text-muted">{data.reading[1]}</p>
                <table className="w-full min-w-[520px] text-[13px]">
                  <thead>
                    <tr className="text-left font-mono text-micro uppercase tracking-wider text-text-dim">
                      <th className="pb-2 pr-3 font-normal">From → to</th>
                      <th className="pb-2 pr-3 text-right font-normal">Error of the model</th>
                      <th className="pb-2 pr-3 text-right font-normal">Error of a naive forecast</th>
                      <th className="pb-2 text-right font-normal">Skill</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.forecast.tests.map((t) => (
                      <tr key={`${t.base_ay}-${t.target_ay}`} className="border-t border-border">
                        <td className="py-1.5 pr-3 font-mono text-text-secondary">
                          {t.base_ay} → {t.target_ay}
                        </td>
                        <td className="py-1.5 pr-3 text-right font-mono">{pct(t.ape_model, 1)}</td>
                        <td className="py-1.5 pr-3 text-right font-mono text-text-muted">{pct(t.ape_naive, 1)}</td>
                        <td className="py-1.5 text-right">
                          {t.skill == null ? (
                            "—"
                          ) : (
                            <Tag tone={t.skill > 0 ? "ok" : "warn"}>{t.skill > 0 ? "beats naive" : "worse than naive"} ({t.skill.toFixed(2)})</Tag>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-2 text-[12px] text-text-dim">
                  The ageing method was chosen on other year pairs before these two were looked at. One pair beats the naive
                  forecast and one does not: the model is not a reliable forecaster of the level of tax in a distant year.
                </p>
              </section>

              <section>
                <h3 className="mb-1 text-[14px] text-text-primary">Does it price a reform as the Budget did?</h3>
                <p className="mb-3 text-[12.5px] leading-relaxed text-text-muted">{data.reading[2]}</p>
                <ul className="space-y-3">
                  {data.reform_cost.map((r) => (
                    <li key={r.reform} className="rounded-[4px] border border-border px-3 py-2.5">
                      <p className="text-[13px] text-text-primary">
                        {r.reform}: simulated {crore(r.simulated_cost_crore)} against {crore(r.announced_cost_crore)} announced
                        <span className="ml-2 font-mono text-[12px] text-status-warning">{r.ratio.toFixed(2)}×</span>
                      </p>
                      <p className="mt-1 text-[12px] leading-relaxed text-text-dim">{r.note}</p>
                    </li>
                  ))}
                </ul>
              </section>

              <section>
                <h3 className="mb-2 text-[14px] text-text-primary">What it does not do</h3>
                <ul className="list-disc space-y-1 pl-5 text-[12.5px] leading-relaxed text-text-muted">
                  {data.limits.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
              </section>
            </>
          )}
        </div>
      )}
    </div>
  );
}
