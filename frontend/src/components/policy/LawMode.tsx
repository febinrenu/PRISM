"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { Callout, ErrorState } from "@/components/ui/kit";
import { Slider } from "@/components/ui/slider";
import LawEditor, { countChanges } from "@/components/policy/LawEditor";
import ProvenanceTable from "@/components/policy/ProvenanceTable";
import ScenarioResults from "@/components/policy/ScenarioResults";
import ValidationPanel from "@/components/policy/ValidationPanel";
import { ASSUMPTION_LABELS, pct } from "@/components/policy/format";
import type {
  PolicyAssumptions, PolicyChanges, PolicyLaw, PolicyLawParams, PolicyLawUnavailable, PolicyScenarioResult, PolicyYear,
} from "@/types";

const DEFAULT_ASSUMPTIONS: PolicyAssumptions = {
  optimal_share: 1.0,
  via_scale: 1.0,
  top_alpha: null,
  senior_share: 0.0,
  growth: 0.096,
};

const DEFAULT_BEHAVIOUR = { audit_rate: 0.01, penalty_rate: 2.0, morale: 0.3 };

/** Only what differs from the baseline goes to the server. */
function changesOf(base: PolicyLawParams, edit: PolicyLawParams): PolicyChanges {
  const c: PolicyChanges = {};
  if (JSON.stringify(base.slabs) !== JSON.stringify(edit.slabs)) c.slabs = edit.slabs;
  if (JSON.stringify(base.rebate) !== JSON.stringify(edit.rebate)) c.rebate = edit.rebate;
  if (base.standard_deduction !== edit.standard_deduction) c.standard_deduction = edit.standard_deduction;
  if (Math.abs(base.cess_rate - edit.cess_rate) > 1e-9) c.cess_rate = edit.cess_rate;
  if (JSON.stringify(base.surcharge) !== JSON.stringify(edit.surcharge)) c.surcharge = edit.surcharge;
  return c;
}

export default function LawMode({ docId, onSwitch }: { docId: string; onSwitch?: () => void }) {
  const [law, setLaw] = useState<PolicyLaw | null>(null);
  const [unavailable, setUnavailable] = useState<PolicyLawUnavailable | null>(null);
  const [years, setYears] = useState<PolicyYear[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [table, setTable] = useState<number | null>(null);
  const [ay, setAy] = useState<string | null>(null);

  const [edit, setEdit] = useState<PolicyLawParams | null>(null);
  const [assumptions, setAssumptions] = useState<PolicyAssumptions>(DEFAULT_ASSUMPTIONS);
  const [behaviourOn, setBehaviourOn] = useState(false);
  const [behaviour, setBehaviour] = useState(DEFAULT_BEHAVIOUR);

  const [result, setResult] = useState<PolicyScenarioResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingFull, setPendingFull] = useState(false);
  const [scenarioError, setScenarioError] = useState<string | null>(null);

  // the baseline law
  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    api
      .policyLaw(docId, ay, table)
      .then((d) => {
        if (cancelled) return;
        if (d.available) {
          setLaw(d);
          setUnavailable(null);
          setEdit(JSON.parse(JSON.stringify(d.law_params)));
          setResult(null);
        } else {
          setLaw(null);
          setUnavailable(d);
        }
      })
      .catch((e) => !cancelled && setLoadError(e instanceof Error ? e.message : "The law could not be loaded."));
    return () => {
      cancelled = true;
    };
  }, [docId, ay, table]);

  // the expert-coded years, offered when a document has no rate table of its own
  useEffect(() => {
    if (!unavailable || years.length) return;
    api.policyYears().then((d) => setYears(d.years)).catch(() => undefined);
  }, [unavailable, years.length]);

  const edited = !!law && !!edit && countChanges(law.law_params, edit) > 0;
  const request = useMemo(() => {
    if (!law || !edit) return null;
    return {
      doc_id: docId,
      ay,
      schedule: law.selected_table,
      changes: changesOf(law.law_params, edit),
      assumptions,
    };
  }, [law, edit, docId, ay, assumptions]);
  const behaviourInput = behaviourOn ? behaviour : null;
  const key = JSON.stringify([request, behaviourInput]);

  // Price the scenario as the person edits: the quick answer first, then (after a pause) the
  // range over the population assumptions and, if asked for, the behavioural response.
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    let slow: ReturnType<typeof setTimeout> | undefined;
    setBusy(true);
    const fast = setTimeout(async () => {
      try {
        const r = await api.policyScenario({ ...request, behaviour: null, uncertainty: 0 }, ctrl.signal);
        setResult(r);
        setScenarioError(null);
        setBusy(false);
        if (r.changes_applied.length > 0) {
          setPendingFull(true);
          slow = setTimeout(async () => {
            try {
              const full = await api.policyScenario({ ...request, behaviour: behaviourInput, uncertainty: 64 }, ctrl.signal);
              setResult(full);
            } catch {
              /* the quick answer stays */
            } finally {
              if (!ctrl.signal.aborted) setPendingFull(false);
            }
          }, 350);
        } else {
          setPendingFull(false);
        }
      } catch (e) {
        if (ctrl.signal.aborted) return;
        setScenarioError(e instanceof Error ? e.message : "The scenario could not be priced.");
        setBusy(false);
        setPendingFull(false);
      }
    }, 220);
    return () => {
      clearTimeout(fast);
      if (slow) clearTimeout(slow);
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (loadError) {
    return <ErrorState title="The law could not be loaded" message={loadError} onRetry={() => setTable((t) => t)} />;
  }

  if (unavailable) {
    return (
      <div className="space-y-4">
        <Callout tone="warn" title="No rate table found in this document">
          {unavailable.reason} The Statute mode prices a change to the law’s own rate schedule. Choose an assessment year’s
          expert-coded law to explore, or switch to Clause dynamics to see how agents respond to this document’s rules.
          {onSwitch && (
            <button type="button" onClick={onSwitch} className="ml-2 text-text-primary underline underline-offset-4">
              Open Clause dynamics
            </button>
          )}
        </Callout>
        <div className="glass-card flex flex-wrap items-center gap-3 p-5">
          <label htmlFor="expert-year" className="text-[13px] text-text-secondary">
            Start from the law of
          </label>
          <select
            id="expert-year"
            value={ay ?? ""}
            onChange={(e) => setAy(e.target.value || null)}
            className="h-9 rounded-[4px] border border-border-light bg-bg-surface px-3 font-mono text-[13px] text-text-primary"
          >
            <option value="">choose a year…</option>
            {years.map((y) => (
              <option key={y.ay} value={y.ay}>
                AY {y.ay} · {y.law === "ITA2025" ? "Income-tax Act 2025" : "Income-tax Act 1961"} · {y.bands} bands
              </option>
            ))}
          </select>
        </div>
      </div>
    );
  }

  if (!law || !edit) {
    return (
      <div role="status" className="flex items-center gap-2 py-16 text-[13px] text-text-muted">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Reading the document’s rate table…
      </div>
    );
  }

  const setA = (patch: Partial<PolicyAssumptions>) => setAssumptions((a) => ({ ...a, ...patch }));
  const bounds = law.bounds;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13px] text-text-secondary">
        <span>
          Baseline: <span className="text-text-primary">{law.title}</span>
          {law.schedule && <span className="text-text-muted"> · page {law.schedule.page}</span>} · AY {law.ay}
          {law.law === "ITA2025" ? " (Income-tax Act 2025)" : " (Income-tax Act 1961)"}
        </span>
        {law.tables.length > 1 && (
          <label className="inline-flex items-center gap-2">
            <span className="text-text-muted">Rate table</span>
            <select
              value={law.selected_table ?? ""}
              onChange={(e) => setTable(Number(e.target.value))}
              className="h-8 rounded-[4px] border border-border-light bg-bg-surface px-2 font-mono text-[12.5px] text-text-primary"
            >
              {law.tables.map((t) => (
                <option key={t.index} value={t.index}>
                  p.{t.page} · {t.bands} bands{t.assessment_year ? ` · AY ${t.assessment_year}` : ""}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,27rem)_minmax(0,1fr)]">
        <div className="space-y-4 xl:sticky xl:top-4">
          <LawEditor baseline={law.law_params} value={edit} onChange={setEdit} error={scenarioError} />

          <details className="glass-card p-5">
            <summary className="cursor-pointer text-[14px] text-text-primary">
              Population assumptions
              <span className="ml-2 font-mono text-micro text-text-dim">what the published statistics do not pin down</span>
            </summary>
            <div className="mt-4 space-y-4">
              {(["optimal_share", "via_scale", "senior_share", "growth"] as const).map((k) => {
                const meta = ASSUMPTION_LABELS[k];
                const [lo, hi] = bounds[k];
                const step = k === "via_scale" ? 0.05 : k === "growth" ? 0.005 : 0.05;
                return (
                  <div key={k}>
                    <div className="mb-1 flex items-center justify-between gap-3">
                      <label className="text-[12.5px] text-text-secondary" title={meta.hint}>
                        {meta.label}
                      </label>
                      <span className="font-mono text-[12.5px] text-text-primary">{meta.format(assumptions[k])}</span>
                    </div>
                    <Slider min={lo} max={hi} step={step} value={[assumptions[k]]} onValueChange={([v]) => setA({ [k]: v })} />
                  </div>
                );
              })}
              <div>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <label className="text-[12.5px] text-text-secondary" title={ASSUMPTION_LABELS.top_alpha.hint}>
                    {ASSUMPTION_LABELS.top_alpha.label}
                  </label>
                  <span className="flex items-center gap-2 font-mono text-[12.5px] text-text-primary">
                    {assumptions.top_alpha == null ? "estimated" : assumptions.top_alpha.toFixed(2)}
                    <label className="inline-flex items-center gap-1 text-text-muted">
                      <input
                        type="checkbox"
                        checked={assumptions.top_alpha == null}
                        onChange={(e) => setA({ top_alpha: e.target.checked ? null : 2.2 })}
                      />
                      auto
                    </label>
                  </span>
                </div>
                <Slider
                  min={bounds.top_alpha[0]}
                  max={bounds.top_alpha[1]}
                  step={0.05}
                  disabled={assumptions.top_alpha == null}
                  value={[assumptions.top_alpha ?? 2.2]}
                  onValueChange={([v]) => setA({ top_alpha: v })}
                />
              </div>
              <button
                type="button"
                onClick={() => setAssumptions(DEFAULT_ASSUMPTIONS)}
                className="font-mono text-micro uppercase tracking-wider text-text-muted underline-offset-4 hover:text-text-primary hover:underline"
              >
                Reset assumptions
              </button>
            </div>
          </details>

          <div className="glass-card p-5">
            <label className="flex items-start gap-3">
              <input type="checkbox" className="mt-1" checked={behaviourOn} onChange={(e) => setBehaviourOn(e.target.checked)} />
              <span>
                <span className="block text-[14px] text-text-primary">Include a behavioural response</span>
                <span className="block text-[12.5px] leading-relaxed text-text-muted">
                  Runs the compliance model under both laws, so the revenue effect includes how evasion responds.
                </span>
              </span>
            </label>
            {behaviourOn && (
              <div className="mt-4 space-y-4">
                {(
                  [
                    ["audit_rate", "Share of returns audited each year", (v: number) => pct(v, 1), 0.005],
                    ["penalty_rate", "Penalty, times the evaded tax", (v: number) => `${v.toFixed(1)}×`, 0.1],
                    ["morale", "Tax morale (mean)", (v: number) => v.toFixed(2), 0.01],
                  ] as const
                ).map(([k, label, fmt, step]) => {
                  const [lo, hi] = law.behaviour_limits[k];
                  return (
                    <div key={k}>
                      <div className="mb-1 flex items-center justify-between gap-3">
                        <span className="text-[12.5px] text-text-secondary">{label}</span>
                        <span className="font-mono text-[12.5px] text-text-primary">{fmt(behaviour[k])}</span>
                      </div>
                      <Slider min={lo} max={Math.min(hi, k === "audit_rate" ? 0.1 : hi)} step={step} value={[behaviour[k]]} onValueChange={([v]) => setBehaviour((b) => ({ ...b, [k]: v }))} />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        <div className="min-w-0">
          {result ? (
            <ScenarioResults
              result={result}
              busy={busy}
              uncertaintyPending={pendingFull && edited}
            />
          ) : (
            <div role="status" className="flex items-center gap-2 py-16 text-[13px] text-text-muted">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Pricing the baseline…
            </div>
          )}
          {behaviourOn && edited && pendingFull && !result?.behaviour && (
            <p role="status" className="mt-3 flex items-center gap-2 text-[12.5px] text-text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> Running the compliance model under both laws…
            </p>
          )}
        </div>
      </div>

      <ProvenanceTable law={law} />
      <ValidationPanel />
    </div>
  );
}
