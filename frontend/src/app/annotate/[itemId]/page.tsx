"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, Loader2, Plus, Save, Trash2, X } from "lucide-react";
import TopNav from "@/components/nav/TopNav";
import { useAuth } from "@/lib/auth";
import { tokens } from "@/lib/tokens";
import {
  AGENT_CLASSES, MODALITIES, annotateApi, emptyRule,
  type AnnRule, type AnnSpan, type Annotation, type ItemView, type Modality, type SetItem,
} from "@/lib/annotate";

type SpanField = "subject" | "action" | "consequence" | "condition" | "exception" | "cross_ref" | "effect";

const FIELD_COLOR: Record<SpanField, string> = {
  subject: tokens.entity.ACTOR.text,
  action: tokens.entity.OBLIGATION.text,
  consequence: tokens.entity.PENALTY.text,
  condition: tokens.status.info,
  exception: tokens.status.warning,
  cross_ref: tokens.entity.RIGHT.text,
  effect: tokens.entity.THRESHOLD.text,
};
const FIELD_LABEL: Record<SpanField, string> = {
  subject: "Subject", action: "Action", consequence: "Consequence", condition: "Condition",
  exception: "Exception", cross_ref: "Cross-reference", effect: "Effect source",
};
const KEYS: Record<string, SpanField> = { s: "subject", a: "action", q: "consequence", c: "condition", e: "exception", r: "cross_ref" };
const NUMERIC = new Set(["lower", "upper", "rate", "max_income", "max_rebate", "amount", "threshold", "max_rate",
  "per_day", "rate_per_month", "max_amount", "days"]);
const CHOICES: Record<string, string[]> = {
  regime: ["both", "old", "new"],
  age_band: ["all", "below_60", "60_to_80", "80_plus"],
};

function spansOf(rule: AnnRule): { span: AnnSpan; field: SpanField }[] {
  const out: { span: AnnSpan; field: SpanField }[] = [];
  if (rule.subject) out.push({ span: rule.subject, field: "subject" });
  if (rule.action) out.push({ span: rule.action, field: "action" });
  if (rule.consequence) out.push({ span: rule.consequence, field: "consequence" });
  rule.conditions.forEach((s) => out.push({ span: s, field: "condition" }));
  rule.exceptions.forEach((s) => out.push({ span: s, field: "exception" }));
  rule.cross_refs.forEach((s) => out.push({ span: s, field: "cross_ref" }));
  rule.effects.forEach((e) => e.source && out.push({ span: e.source, field: "effect" }));
  return out;
}

function Highlighted({ text, rule, onRef }: { text: string; rule: AnnRule | null; onRef: (el: HTMLDivElement | null) => void }) {
  const marks = rule ? spansOf(rule) : [];
  const cuts = new Set<number>([0, text.length]);
  marks.forEach(({ span }) => { cuts.add(span.start); cuts.add(span.end); });
  const bounds = Array.from(cuts).filter((c) => c >= 0 && c <= text.length).sort((a, b) => a - b);
  const segments = bounds.slice(0, -1).map((s, i) => {
    const e = bounds[i + 1];
    const covering = marks.filter((m) => m.span.start <= s && m.span.end >= e);
    const top = covering[covering.length - 1];
    return { s, e, field: top?.field };
  });
  return (
    <div ref={onRef} className="whitespace-pre-wrap leading-7 text-[15px] text-text-primary select-text" style={{ fontFamily: "Georgia, serif" }}>
      {segments.map((seg) => (
        <span
          key={seg.s}
          data-start={seg.s}
          title={seg.field ? FIELD_LABEL[seg.field] : undefined}
          style={seg.field ? { backgroundColor: `${FIELD_COLOR[seg.field]}33`, borderBottom: `2px solid ${FIELD_COLOR[seg.field]}` } : undefined}
        >
          {text.slice(seg.s, seg.e)}
        </span>
      ))}
    </div>
  );
}

export default function AnnotateItem() {
  const { itemId } = useParams<{ itemId: string }>();
  const search = useSearchParams();
  const set = search.get("set") || "pilot";
  const router = useRouter();
  const { user, loading } = useAuth();

  const [view, setView] = useState<ItemView | null>(null);
  const [ann, setAnn] = useState<Annotation>({ status: "draft", no_rule: false, rules: [emptyRule()], seconds: 0, note: "" });
  const [active, setActive] = useState(0);
  const [siblings, setSiblings] = useState<SetItem[]>([]);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const textRef = useRef<HTMLDivElement | null>(null);
  const started = useRef<number>(Date.now());

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user || !itemId) return;
    setView(null);
    setMessage(null);
    annotateApi.item(itemId).then((v) => {
      setView(v);
      const a = v.annotation;
      setAnn(a ? { ...a, rules: a.rules.length ? a.rules : (a.no_rule ? [] : [emptyRule()]) } :
        { status: "draft", no_rule: false, rules: [emptyRule()], seconds: 0, note: "" });
      setActive(0);
      setDirty(false);
      started.current = Date.now();
    }).catch((e) => setMessage({ kind: "error", text: String(e.message || e) }));
    annotateApi.items(set).then((r) => setSiblings(r.items)).catch(() => {});
  }, [user, itemId, set]);

  const index = siblings.findIndex((s) => s.item_id === itemId);
  const prev = index > 0 ? siblings[index - 1] : null;
  const next = index >= 0 && index < siblings.length - 1 ? siblings[index + 1] : null;
  const rule = ann.rules[active] ?? null;

  const update = useCallback((fn: (r: AnnRule) => AnnRule) => {
    setAnn((a) => ({ ...a, rules: a.rules.map((r, i) => (i === active ? fn(r) : r)) }));
    setDirty(true);
  }, [active]);

  const selection = useCallback((): AnnSpan | null => {
    const sel = window.getSelection();
    const root = textRef.current;
    if (!sel || sel.rangeCount === 0 || !root || sel.isCollapsed) return null;
    const offsetOf = (node: Node | null, offset: number): number | null => {
      let el: Node | null = node;
      while (el && el !== root && !(el instanceof HTMLElement && el.dataset.start)) el = el.parentNode;
      if (!el || !(el instanceof HTMLElement) || !el.dataset.start) return null;
      return Number(el.dataset.start) + offset;
    };
    const a = offsetOf(sel.anchorNode, sel.anchorOffset);
    const b = offsetOf(sel.focusNode, sel.focusOffset);
    if (a === null || b === null) return null;
    let start = Math.min(a, b);
    let end = Math.max(a, b);
    const text = view?.text ?? "";
    while (start < end && /\s/.test(text[start])) start++;
    while (end > start && /\s/.test(text[end - 1])) end--;
    return end > start ? { start, end } : null;
  }, [view]);

  const assign = useCallback((field: SpanField) => {
    const span = selection();
    if (!span) {
      setMessage({ kind: "error", text: "Select some text in the provision first." });
      return;
    }
    setMessage(null);
    update((r) => {
      switch (field) {
        case "subject": return { ...r, subject: span };
        case "action": return { ...r, action: span };
        case "consequence": return { ...r, consequence: span };
        case "condition": return { ...r, conditions: [...r.conditions, { ...span, negated: false }] };
        case "exception": return { ...r, exceptions: [...r.exceptions, span] };
        case "cross_ref": return { ...r, cross_refs: [...r.cross_refs, span] };
        default: return r;
      }
    });
    window.getSelection()?.removeAllRanges();
  }, [selection, update]);

  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => {
      const t = ev.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || ev.ctrlKey || ev.metaKey || ev.altKey) return;
      const f = KEYS[ev.key.toLowerCase()];
      if (f) {
        ev.preventDefault();
        assign(f);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [assign]);

  const save = async (status: "draft" | "done", goNext = false) => {
    if (!itemId) return;
    setSaving(true);
    const seconds = (ann.seconds || 0) + Math.round((Date.now() - started.current) / 1000);
    const payload: Annotation = {
      ...ann, status, seconds,
      rules: ann.no_rule ? [] : ann.rules.map((r) => ({
        ...r,
        effects: r.effects.map((e) => ({
          ...e,
          fields: Object.fromEntries(Object.entries(e.fields).filter(([, v]) => v !== "" && v !== null)),
        })),
      })),
    };
    try {
      const res = await annotateApi.save(itemId, payload);
      started.current = Date.now();
      setAnn({ ...payload });
      setDirty(false);
      setMessage({ kind: "ok", text: res.warnings.length ? `Saved with warnings: ${res.warnings.join("; ")}` : status === "done" ? "Marked done." : "Draft saved." });
      if (goNext && next) router.push(`/annotate/${next.item_id}?set=${set}`);
    } catch (e) {
      setMessage({ kind: "error", text: String((e as Error).message || e) });
    } finally {
      setSaving(false);
    }
  };

  const spanText = (s: AnnSpan | null) => (s && view ? view.text.slice(s.start, s.end) : "");
  const effectFields = useMemo(() => view?.effect_fields ?? {}, [view]);

  if (loading || !user || !view) {
    return (
      <main className="min-h-screen bg-bg-base flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-accent-primary" />
        {message && <p className="text-sm text-status-error" role="alert">{message.text}</p>}
      </main>
    );
  }

  const SpanChip = ({ s, field, onRemove, extra }: { s: AnnSpan; field: SpanField; onRemove: () => void; extra?: React.ReactNode }) => (
    <div className="flex items-start gap-2 text-sm rounded-sm px-2 py-1.5 bg-bg-base border-l-2" style={{ borderColor: FIELD_COLOR[field] }}>
      <span className="flex-1 text-text-secondary">“{spanText(s)}”</span>
      {extra}
      <button onClick={onRemove} aria-label={`Remove ${FIELD_LABEL[field]}`} className="text-text-dim hover:text-status-error"><X className="w-3.5 h-3.5" /></button>
    </div>
  );

  return (
    <main className="relative min-h-screen app-shell bg-bg-base text-text-primary">
      <TopNav />
      <div className="relative z-10 max-w-[1400px] mx-auto px-4 sm:px-6 py-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <Link href="/annotate" className="text-text-muted hover:text-text-primary" aria-label="Back to sets"><ArrowLeft className="w-4 h-4" /></Link>
            <div>
              <h1 className="font-mono text-sm">{view.item.item_id}</h1>
              <p className="text-xs text-text-muted">{view.item.statute} · {view.item.path} {index >= 0 && `· ${index + 1} of ${siblings.length}`}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {prev && <Link href={`/annotate/${prev.item_id}?set=${set}`} className="px-2 py-1.5 text-xs border border-border rounded-sm hover:border-border-light"><ArrowLeft className="w-3.5 h-3.5 inline" /> Prev</Link>}
            <button disabled={saving} onClick={() => save("draft")} className="px-3 py-1.5 text-xs border border-border rounded-sm hover:border-border-light disabled:opacity-50">
              <Save className="w-3.5 h-3.5 inline mr-1" />Save draft{dirty ? " •" : ""}
            </button>
            <button disabled={saving} onClick={() => save("done", true)} className="px-3 py-1.5 text-xs rounded-sm bg-accent-primary text-text-inverse disabled:opacity-50">
              Done{next ? " & next" : ""} <ArrowRight className="w-3.5 h-3.5 inline" />
            </button>
          </div>
        </div>

        {message && (
          <p role="status" className={`text-sm mb-3 ${message.kind === "error" ? "text-status-error" : "text-status-success"}`}>{message.text}</p>
        )}

        <div className="grid lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] gap-5">
          {/* Provision */}
          <section className="space-y-3">
            {(view.heading || view.context) && (
              <div className="text-xs text-text-muted bg-bg-surface border border-border rounded-sm p-3 whitespace-pre-wrap">
                <span className="font-mono uppercase tracking-wider text-[11px] text-text-dim">Context (do not annotate)</span>
                <div className="mt-1">{view.context || view.heading}</div>
              </div>
            )}
            <div className="bg-bg-surface border border-border rounded-sm p-4">
              <Highlighted text={view.text} rule={rule} onRef={(el) => { textRef.current = el; }} />
            </div>
            <div className="flex flex-wrap gap-2" aria-label="Assign selection">
              {(Object.keys(KEYS) as string[]).map((k) => (
                <button key={k} onClick={() => assign(KEYS[k])} disabled={!rule || ann.no_rule}
                  className="text-xs px-2.5 py-1.5 rounded-sm border border-border hover:border-border-light disabled:opacity-40"
                  style={{ borderLeft: `3px solid ${FIELD_COLOR[KEYS[k]]}` }}>
                  {FIELD_LABEL[KEYS[k]]} <span className="font-mono text-text-dim">[{k.toUpperCase()}]</span>
                </button>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm text-text-secondary">
              <input type="checkbox" checked={ann.no_rule}
                onChange={(e) => { setAnn((a) => ({ ...a, no_rule: e.target.checked })); setDirty(true); }} />
              This provision states no rule (a heading, a commencement clause, a bare list item)
            </label>
          </section>

          {/* Rules */}
          {!ann.no_rule && (
            <section className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                {ann.rules.map((_, i) => (
                  <button key={i} onClick={() => setActive(i)}
                    className={`text-xs px-2.5 py-1.5 rounded-sm border ${i === active ? "border-accent-primary bg-bg-elevated" : "border-border"}`}>
                    Rule {i + 1}
                  </button>
                ))}
                <button onClick={() => { setAnn((a) => ({ ...a, rules: [...a.rules, emptyRule()] })); setActive(ann.rules.length); setDirty(true); }}
                  className="text-xs px-2.5 py-1.5 rounded-sm border border-dashed border-border-light"><Plus className="w-3 h-3 inline" /> Rule</button>
                {ann.rules.length > 1 && (
                  <button onClick={() => { setAnn((a) => ({ ...a, rules: a.rules.filter((_, i) => i !== active) })); setActive(0); setDirty(true); }}
                    className="text-xs px-2 py-1.5 text-text-dim hover:text-status-error" aria-label="Delete this rule"><Trash2 className="w-3.5 h-3.5" /></button>
                )}
              </div>

              {rule && (
                <div className="bg-bg-surface border border-border rounded-sm p-4 space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <label className="text-xs text-text-muted">Modality
                      <select value={rule.modality} onChange={(e) => update((r) => ({ ...r, modality: e.target.value as Modality }))}
                        className="mt-1 w-full bg-bg-base border border-border rounded-sm px-2 py-1.5 text-sm text-text-primary">
                        {MODALITIES.map((m) => <option key={m} value={m}>{m}</option>)}
                      </select>
                    </label>
                    <label className="text-xs text-text-muted">Who it binds
                      <select value={rule.agent_class ?? ""} onChange={(e) => update((r) => ({ ...r, agent_class: e.target.value || null }))}
                        className="mt-1 w-full bg-bg-base border border-border rounded-sm px-2 py-1.5 text-sm text-text-primary">
                        <option value="">—</option>
                        {AGENT_CLASSES.map((a) => <option key={a} value={a}>{a}</option>)}
                      </select>
                    </label>
                  </div>

                  {(["subject", "action", "consequence"] as const).map((f) => (
                    <div key={f}>
                      <p className="text-xs text-text-muted mb-1">{FIELD_LABEL[f]}</p>
                      {rule[f] ? <SpanChip s={rule[f] as AnnSpan} field={f} onRemove={() => update((r) => ({ ...r, [f]: null }))} />
                        : <p className="text-xs text-text-dim">Select text and press [{Object.keys(KEYS).find((k) => KEYS[k] === f)?.toUpperCase()}]</p>}
                    </div>
                  ))}

                  {([["condition", "conditions"], ["exception", "exceptions"], ["cross_ref", "cross_refs"]] as const).map(([f, key]) => (
                    <div key={key}>
                      <p className="text-xs text-text-muted mb-1">{FIELD_LABEL[f]}s</p>
                      <div className="space-y-1.5">
                        {(rule[key] as AnnSpan[]).map((s, i) => (
                          <SpanChip key={i} s={s} field={f}
                            onRemove={() => update((r) => ({ ...r, [key]: (r[key] as AnnSpan[]).filter((_, j) => j !== i) }))}
                            extra={f === "condition" ? (
                              <label className="text-[11px] text-text-muted flex items-center gap-1">
                                <input type="checkbox" checked={rule.conditions[i].negated}
                                  onChange={(e) => update((r) => ({ ...r, conditions: r.conditions.map((c, j) => j === i ? { ...c, negated: e.target.checked } : c) }))} />
                                negated
                              </label>
                            ) : undefined} />
                        ))}
                      </div>
                    </div>
                  ))}

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs text-text-muted">Effects (numbers the rule sets)</p>
                      <select value="" onChange={(e) => {
                        const kind = e.target.value;
                        if (kind) update((r) => ({ ...r, effects: [...r.effects, { kind, fields: {}, source: null }] }));
                      }} className="bg-bg-base border border-border rounded-sm px-2 py-1 text-xs text-text-primary" aria-label="Add effect">
                        <option value="">+ add effect…</option>
                        {Object.keys(effectFields).map((k) => <option key={k} value={k}>{k}</option>)}
                      </select>
                    </div>
                    <div className="space-y-2">
                      {rule.effects.map((eff, i) => (
                        <div key={i} className="border border-border rounded-sm p-2.5 space-y-2" style={{ borderLeft: `3px solid ${FIELD_COLOR.effect}` }}>
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-xs">{eff.kind}</span>
                            <button onClick={() => update((r) => ({ ...r, effects: r.effects.filter((_, j) => j !== i) }))}
                              className="text-text-dim hover:text-status-error" aria-label="Remove effect"><X className="w-3.5 h-3.5" /></button>
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                            {(effectFields[eff.kind] ?? []).map((f) => (
                              <label key={f} className="text-[11px] text-text-muted">{f}
                                {f === "marginal_relief" ? (
                                  <input type="checkbox" className="ml-2 align-middle" checked={Boolean(eff.fields[f])}
                                    onChange={(e) => update((r) => ({ ...r, effects: r.effects.map((x, j) => j === i ? { ...x, fields: { ...x.fields, [f]: e.target.checked } } : x) }))} />
                                ) : CHOICES[f] ? (
                                  <select value={String(eff.fields[f] ?? CHOICES[f][0])}
                                    onChange={(e) => update((r) => ({ ...r, effects: r.effects.map((x, j) => j === i ? { ...x, fields: { ...x.fields, [f]: e.target.value } } : x) }))}
                                    className="mt-0.5 w-full bg-bg-base border border-border rounded-sm px-1.5 py-1 text-xs text-text-primary">
                                    {CHOICES[f].map((c) => <option key={c} value={c}>{c}</option>)}
                                  </select>
                                ) : (
                                  <input value={eff.fields[f] === null || eff.fields[f] === undefined ? "" : String(eff.fields[f])}
                                    inputMode={NUMERIC.has(f) ? "decimal" : "text"}
                                    placeholder={NUMERIC.has(f) ? (f.includes("rate") ? "0.05" : "rupees") : ""}
                                    onChange={(e) => {
                                      const raw = e.target.value;
                                      const v = NUMERIC.has(f) && raw !== "" && !Number.isNaN(Number(raw)) ? Number(raw) : raw;
                                      update((r) => ({ ...r, effects: r.effects.map((x, j) => j === i ? { ...x, fields: { ...x.fields, [f]: v } } : x) }));
                                    }}
                                    className="mt-0.5 w-full bg-bg-base border border-border rounded-sm px-1.5 py-1 text-xs text-text-primary" />
                                )}
                              </label>
                            ))}
                          </div>
                          <div className="flex items-center gap-2">
                            <button onClick={() => {
                              const span = selection();
                              if (!span) { setMessage({ kind: "error", text: "Select the words the numbers come from first." }); return; }
                              update((r) => ({ ...r, effects: r.effects.map((x, j) => j === i ? { ...x, source: span } : x) }));
                            }} className="text-[11px] px-2 py-1 border border-border rounded-sm hover:border-border-light">Source ← selection</button>
                            {eff.source && <span className="text-[11px] text-text-muted truncate">“{spanText(eff.source)}”</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid gap-2">
                    <label className="flex items-center gap-2 text-xs text-text-secondary">
                      <input type="checkbox" checked={rule.executable} onChange={(e) => update((r) => ({ ...r, executable: e.target.checked }))} />
                      Executable: the rule&apos;s conditions can be decided from facts (income, days late, turnover …)
                    </label>
                    <label className="text-xs text-text-muted">Note
                      <textarea value={rule.note} onChange={(e) => update((r) => ({ ...r, note: e.target.value }))} rows={2}
                        className="mt-1 w-full bg-bg-base border border-border rounded-sm px-2 py-1.5 text-sm text-text-primary" />
                    </label>
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    </main>
  );
}
