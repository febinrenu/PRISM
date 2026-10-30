"use client";

import { useMemo } from "react";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import NumField from "@/components/policy/NumField";
import { inr, pct, slabTax } from "@/components/policy/format";
import type { PolicyLawParams, PolicySlab } from "@/types";

const LAKH = 1e5;

interface Preset {
  id: string;
  label: string;
  apply: (base: PolicyLawParams) => PolicyLawParams;
}

const clone = (p: PolicyLawParams): PolicyLawParams => JSON.parse(JSON.stringify(p));

/** One-click changes, each relative to the baseline law (not to one another), so
 *  they are ways in to the editor, not a menu of results. */
function presetsFor(base: PolicyLawParams): Preset[] {
  const out: Preset[] = [];
  const firstTaxed = base.slabs.findIndex((s) => s.rate > 0);
  if (firstTaxed >= 0) {
    const cut = Math.max(0, base.slabs[firstTaxed].rate - 0.02);
    out.push({
      id: "cut",
      label: `Cut the ${pct(base.slabs[firstTaxed].rate, 0)} band to ${pct(cut, 0)}`,
      apply: (b) => {
        const p = clone(b);
        p.slabs[firstTaxed].rate = cut;
        return p;
      },
    });
  }
  const target = base.rebate ? base.rebate.max_income + 3 * LAKH : 5 * LAKH;
  out.push({
    id: "taxfree",
    label: `Make income up to ${inr(target)} tax-free`,
    apply: (b) => {
      const p = clone(b);
      p.rebate = {
        max_income: target,
        max_rebate: Math.ceil(slabTax(target, b.slabs)),
        marginal_relief: b.rebate?.marginal_relief ?? true,
      };
      return p;
    },
  });
  out.push({
    id: "sd",
    label: `Raise the standard deduction to ${inr(base.standard_deduction + 25000)}`,
    apply: (b) => {
      const p = clone(b);
      p.standard_deduction = b.standard_deduction + 25000;
      return p;
    },
  });
  const last = base.slabs[base.slabs.length - 1];
  if (last.rate < 0.9) {
    const at = last.lower < 50 * LAKH ? 50 * LAKH : Math.round((last.lower * 1.5) / LAKH) * LAKH;
    out.push({
      id: "top",
      label: `Add a band of ${pct(Math.min(0.9, last.rate + 0.05), 0)} above ${inr(at)}`,
      apply: (b) => {
        const p = clone(b);
        const l = p.slabs[p.slabs.length - 1];
        p.slabs.push({ lower: at, upper: null, rate: Math.min(0.9, l.rate + 0.05) });
        l.upper = at;
        return p;
      },
    });
  }
  if (base.rebate) {
    out.push({
      id: "norebate",
      label: "Abolish the rebate",
      apply: (b) => ({ ...clone(b), rebate: null }),
    });
  }
  return out;
}

export function countChanges(base: PolicyLawParams, edit: PolicyLawParams): number {
  let n = 0;
  if (JSON.stringify(base.slabs) !== JSON.stringify(edit.slabs)) {
    if (base.slabs.length !== edit.slabs.length) n += 1;
    else
      base.slabs.forEach((s, i) => {
        if (Math.abs(s.rate - edit.slabs[i].rate) > 1e-9) n += 1;
        if (i < base.slabs.length - 1 && s.upper !== edit.slabs[i].upper) n += 1;
      });
  }
  if (JSON.stringify(base.rebate) !== JSON.stringify(edit.rebate)) n += 1;
  if (base.standard_deduction !== edit.standard_deduction) n += 1;
  if (Math.abs(base.cess_rate - edit.cess_rate) > 1e-9) n += 1;
  return n;
}

export default function LawEditor({
  baseline,
  value,
  onChange,
  disabled,
  error,
}: {
  baseline: PolicyLawParams;
  value: PolicyLawParams;
  onChange: (next: PolicyLawParams) => void;
  disabled?: boolean;
  error?: string | null;
}) {
  const presets = useMemo(() => presetsFor(baseline), [baseline]);
  const changes = countChanges(baseline, value);
  const slabs = value.slabs;

  const setSlab = (i: number, patch: Partial<PolicySlab>) => {
    const next = clone(value);
    Object.assign(next.slabs[i], patch);
    if (patch.upper !== undefined && patch.upper !== null && next.slabs[i + 1]) next.slabs[i + 1].lower = patch.upper;
    onChange(next);
  };

  const addBand = () => {
    const next = clone(value);
    const l = next.slabs[next.slabs.length - 1];
    const at = Math.max(l.lower + 5 * LAKH, Math.round((l.lower * 1.5) / LAKH) * LAKH);
    next.slabs.push({ lower: at, upper: null, rate: Math.min(0.9, l.rate + 0.05) });
    l.upper = at;
    onChange(next);
  };

  const removeBand = () => {
    if (slabs.length <= 2) return;
    const next = clone(value);
    next.slabs.pop();
    next.slabs[next.slabs.length - 1].upper = null;
    onChange(next);
  };

  const changed = (a: number, b: number) => Math.abs(a - b) > 1e-9;
  const mark = (isChanged: boolean) => (isChanged ? "ring-1 ring-signal/50" : "");

  return (
    <div className="glass-card p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="kicker mb-1">Change the law</div>
          <p className="text-[13px] text-text-muted">
            {changes === 0 ? "Nothing changed yet: this is the baseline." : `${changes} change${changes > 1 ? "s" : ""} to the baseline.`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onChange(clone(baseline))}
          disabled={disabled || changes === 0}
          className="inline-flex h-8 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary disabled:opacity-40"
        >
          <RotateCcw className="h-3.5 w-3.5" aria-hidden /> Reset
        </button>
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        {presets.map((p) => (
          <button
            key={p.id}
            type="button"
            disabled={disabled}
            onClick={() => onChange(p.apply(baseline))}
            className="rounded-full border border-border px-3 py-1 text-[12.5px] text-text-secondary transition-colors hover:border-signal/50 hover:text-text-primary disabled:opacity-50"
          >
            {p.label}
          </button>
        ))}
      </div>

      <p className="mb-1 font-mono text-micro text-text-dim">Income limits in ₹ lakh; rates in %</p>
      <div>
        <table className="w-full table-fixed text-[13px]">
          <caption className="sr-only">Income-tax slabs: income from, income up to (in lakh rupees), rate of tax</caption>
          <colgroup>
            <col className="w-9" />
            <col />
            <col />
            <col />
          </colgroup>
          <thead>
            <tr className="text-left font-mono text-micro uppercase tracking-wider text-text-dim">
              <th className="pb-2 pr-2 font-normal">Band</th>
              <th className="pb-2 pr-2 text-right font-normal">From</th>
              <th className="pb-2 pr-2 text-right font-normal">Up to</th>
              <th className="pb-2 text-right font-normal">Rate</th>
            </tr>
          </thead>
          <tbody>
            {slabs.map((s, i) => {
              const b = baseline.slabs[i];
              const last = i === slabs.length - 1;
              const rateChanged = !b || changed(b.rate, s.rate);
              const upperChanged = !!b && !last && b.upper !== s.upper;
              return (
                <tr key={i} className="border-t border-border">
                  <td className="py-1.5 pr-2 font-mono text-text-muted">{i + 1}</td>
                  <td className="py-1.5 pr-2 text-right font-mono text-text-secondary">{Number((s.lower / LAKH).toFixed(2))}</td>
                  <td className="py-1.5 pr-2">
                    {last ? (
                      <span className="block text-right font-mono text-text-dim">and above</span>
                    ) : (
                      <NumField
                        label={`Band ${i + 1} upper limit in lakh rupees`}
                        value={s.upper ?? 0}
                        scale={1 / LAKH}
                        min={s.lower / LAKH + 0.01}
                        step={0.5}
                        disabled={disabled}
                        className={cn("w-full rounded-[4px]", mark(upperChanged))}
                        onCommit={(v) => setSlab(i, { upper: v })}
                      />
                    )}
                    {upperChanged && b?.upper != null && (
                      <span className="mt-0.5 block text-right font-mono text-[11px] text-text-dim">was {Number((b.upper / LAKH).toFixed(2))}</span>
                    )}
                  </td>
                  <td className="py-1.5 text-right">
                    <NumField
                      label={`Band ${i + 1} rate in percent`}
                      value={s.rate}
                      scale={100}
                      min={0}
                      max={100}
                      step={1}
                      suffix="%"
                      disabled={disabled}
                      className={cn("w-full rounded-[4px]", mark(rateChanged))}
                      onCommit={(v) => setSlab(i, { rate: v })}
                    />
                    {rateChanged && b && (
                      <span className="mt-0.5 block text-right font-mono text-[11px] text-text-dim">was {pct(b.rate, 0)}</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={addBand}
          disabled={disabled || slabs.length >= 12}
          className="inline-flex h-8 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary disabled:opacity-40"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden /> Add a top band
        </button>
        <button
          type="button"
          onClick={removeBand}
          disabled={disabled || slabs.length <= 2}
          className="inline-flex h-8 items-center gap-1.5 rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary disabled:opacity-40"
        >
          <Minus className="h-3.5 w-3.5" aria-hidden /> Remove the top band
        </button>
      </div>

      <div className="mt-6 grid gap-5 border-t border-border pt-5 sm:grid-cols-2">
        <fieldset className="space-y-2.5">
          <legend className="mb-1 flex items-center gap-3 text-[13px] text-text-primary">
            Rebate
            <label className="inline-flex items-center gap-1.5 font-mono text-[12px] text-text-muted">
              <input
                type="checkbox"
                checked={value.rebate !== null}
                disabled={disabled}
                onChange={(e) =>
                  onChange({
                    ...value,
                    rebate: e.target.checked ? (baseline.rebate ?? { max_income: 5 * LAKH, max_rebate: 12500, marginal_relief: false }) : null,
                  })
                }
              />
              applies
            </label>
          </legend>
          {value.rebate && (
            <>
              <label className="flex items-center justify-between gap-3 text-[12.5px] text-text-secondary">
                Income up to (₹ lakh)
                <NumField
                  label="Rebate income limit in lakh rupees"
                  value={value.rebate.max_income}
                  scale={1 / LAKH}
                  min={0}
                  step={0.5}
                  disabled={disabled}
                  className={cn("w-28 rounded-[4px]", mark(!baseline.rebate || changed(baseline.rebate.max_income, value.rebate.max_income)))}
                  onCommit={(v) => onChange({ ...value, rebate: { ...value.rebate!, max_income: v } })}
                />
              </label>
              <label className="flex items-center justify-between gap-3 text-[12.5px] text-text-secondary">
                Rebate of up to (₹)
                <NumField
                  label="Maximum rebate in rupees"
                  value={value.rebate.max_rebate}
                  min={0}
                  step={5000}
                  disabled={disabled}
                  className={cn("w-28 rounded-[4px]", mark(!baseline.rebate || changed(baseline.rebate.max_rebate, value.rebate.max_rebate)))}
                  onCommit={(v) => onChange({ ...value, rebate: { ...value.rebate!, max_rebate: v } })}
                />
              </label>
              <label className="flex items-center gap-2 text-[12.5px] text-text-secondary">
                <input
                  type="checkbox"
                  checked={value.rebate.marginal_relief}
                  disabled={disabled}
                  onChange={(e) => onChange({ ...value, rebate: { ...value.rebate!, marginal_relief: e.target.checked } })}
                />
                Marginal relief just above the limit
              </label>
            </>
          )}
        </fieldset>

        <div className="space-y-2.5">
          <label className="flex items-center justify-between gap-3 text-[12.5px] text-text-secondary">
            Standard deduction (₹)
            <NumField
              label="Standard deduction in rupees"
              value={value.standard_deduction}
              min={0}
              step={5000}
              disabled={disabled}
              className={cn("w-28 rounded-[4px]", mark(changed(baseline.standard_deduction, value.standard_deduction)))}
              onCommit={(v) => onChange({ ...value, standard_deduction: v })}
            />
          </label>
          <label className="flex items-center justify-between gap-3 text-[12.5px] text-text-secondary">
            Health and education cess
            <NumField
              label="Cess rate in percent"
              value={value.cess_rate}
              scale={100}
              min={0}
              max={20}
              step={0.5}
              suffix="%"
              disabled={disabled}
              className={cn("w-28 rounded-[4px]", mark(changed(baseline.cess_rate, value.cess_rate)))}
              onCommit={(v) => onChange({ ...value, cess_rate: v })}
            />
          </label>
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-[4px] border border-status-error/40 bg-status-error/[0.07] px-3 py-2 text-[13px] text-status-error">
          {error}
        </p>
      )}
    </div>
  );
}
