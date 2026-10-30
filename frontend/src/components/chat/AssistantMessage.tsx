"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle, BookOpen, Check, ChevronDown, Clock, Cloud, CornerDownRight, Cpu, Loader2, Scale,
  SearchX, ShieldAlert, ShieldCheck, Target,
} from "lucide-react";
import { cn } from "@/lib/utils";
import AnswerText from "@/components/chat/AnswerText";
import CitationCard from "@/components/chat/CitationCard";
import type { ChatMessage, RAGPlan } from "@/types";

const ACT_NAMES: Record<string, string> = {
  ITA1961: "Income-tax Act, 1961",
  ITA2025: "Income-tax Act, 2025",
  CGST2017: "CGST Act, 2017",
  COW2019: "Code on Wages, 2019",
  DPDP2023: "DPDP Act, 2023",
};

function actLabel(key: string): string {
  const [id, version] = key.split("/");
  const name = ACT_NAMES[id] ?? id.replace(/^FA(\d{4})N2$/, "Finance (No. 2) Act, $1").replace(/^FA(\d{4})$/, "Finance Act, $1");
  return version ? `${name} (${version.replace("_", " ")})` : name;
}

function seconds(ms?: number): string | null {
  return ms == null ? null : `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)} s`;
}

function PlanStrip({ plan }: { plan: RAGPlan }) {
  const chips: { icon: React.ReactNode; text: string }[] = [];
  if (plan.intent === "compare") chips.push({ icon: <Scale className="h-3 w-3" aria-hidden />, text: "comparing Acts" });
  for (const s of plan.sections) chips.push({ icon: <Target className="h-3 w-3" aria-hidden />, text: `section ${s}` });
  for (const a of plan.acts) chips.push({ icon: <BookOpen className="h-3 w-3" aria-hidden />, text: actLabel(a) });
  if (!plan.standalone && chips.length === 0) return null;
  return (
    <div className="mb-2 space-y-1.5">
      {plan.standalone && (
        <p className="flex items-start gap-1.5 font-mono text-micro text-text-muted">
          <CornerDownRight className="mt-0.5 h-3 w-3 shrink-0" aria-hidden />
          <span>
            Understood as: <span className="text-text-secondary">{plan.standalone}</span>
          </span>
        </p>
      )}
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {chips.map((c, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-sm border border-border px-1.5 py-0.5 font-mono text-micro text-text-secondary"
            >
              {c.icon}
              {c.text}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AssistantMessage({
  message: m,
  onFollowUp,
}: {
  message: ChatMessage;
  onFollowUp?: (q: string) => void;
}) {
  const [openCards, setOpenCards] = useState<Set<number>>(new Set());
  const [showClaims, setShowClaims] = useState(false);
  const [showOthers, setShowOthers] = useState(false);

  const verdict = m.verdict;
  const state = verdict?.state;
  const cited = useMemo(() => new Set(verdict?.cited_sources ?? []), [verdict]);
  const all = m.citations ?? [];
  const finished = !!verdict;
  // once the verdict is in, the cited passages lead and the rest fold away (when it
  // cites none, every retrieved passage stays in view)
  const citedOnly = finished && state !== "not_found" && cited.size > 0;
  const primary = citedOnly ? all.filter((c) => cited.has(c.index)) : all;
  const others = citedOnly ? all.filter((c) => !cited.has(c.index)) : [];

  const toggleCard = (n: number) =>
    setOpenCards((prev) => {
      const next = new Set(prev);
      next.has(n) ? next.delete(n) : next.add(n);
      return next;
    });

  const openCited = (n: number) => {
    setOpenCards((prev) => new Set(prev).add(n));
    if (!primary.some((c) => c.index === n)) setShowOthers(true);
    requestAnimationFrame(() =>
      document.getElementById(`source-${n}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" })
    );
  };

  const flagged = verdict ? verdict.claims.filter((c) => c.status !== "supported") : [];
  const conflicts = verdict?.n_conflicts ?? flagged.filter((c) => c.status === "unsupported").length;
  const uncited = verdict?.n_uncited ?? flagged.filter((c) => c.status === "uncited").length;
  const headline = !verdict
    ? ""
    : state === "answered"
      ? uncited === 0
        ? `Checked against the sources: all ${verdict.n_claims} statements supported`
        : `No figure or quotation conflicts with the cited text · ${uncited} of ${verdict.n_claims} statements carry no citation`
      : conflicts > 0
        ? `${conflicts} ${conflicts === 1 ? "statement conflicts" : "statements conflict"} with the cited text`
        : "No source is cited for this answer";
  const modelLine = m.backendUsed
    ? `${m.backendUsed.model}${m.backendUsed.fell_back ? " (fallback)" : ""}`
    : null;
  const total = seconds(m.latencyMs?.total);

  const followUps = useMemo(() => {
    if (state !== "answered" && state !== "partial") return [];
    const out = ["What are the conditions or exceptions?", "Explain this with a worked example"];
    const docs = new Set(primary.map((c) => c.doc_name));
    if (docs.size === 1 && primary[0]?.kind === "statute" && primary[0].section) {
      out.unshift(`Show the full text of section ${primary[0].section.replace(/\(.*$/, "")}`);
    }
    return out.slice(0, 3);
  }, [state, primary]);

  const tone =
    state === "answered" ? "border-status-success/35" :
    state === "partial" ? "border-status-warning/45" :
    state === "not_found" ? "border-border-light" : "border-border";

  return (
    <div className="w-full max-w-[94%]">
      {m.plan && <PlanStrip plan={m.plan} />}

      <div className={cn("rounded-lg rounded-tl-sm border bg-bg-surface p-4", tone)}>
        {state === "not_found" && (
          <div className="mb-2 flex items-center gap-2 font-mono text-micro uppercase tracking-widest text-text-muted">
            <SearchX className="h-3.5 w-3.5" aria-hidden /> Not in the corpus
          </div>
        )}

        {m.content ? (
          <AnswerText
            text={m.content}
            unsupported={verdict?.unsupported_numbers}
            invalid={verdict?.invalid_citations}
            onCite={openCited}
            streaming={m.streaming}
          />
        ) : !m.error ? (
          <p className="flex items-center gap-2 text-[13px] text-text-muted">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            {m.plan?.standalone || m.plan?.sections.length ? "Fetching the cited provisions…" : "Searching the statutes…"}
          </p>
        ) : null}

        {m.revising && (
          <p className="mt-3 flex items-center gap-2 rounded-sm border border-status-warning/40 bg-status-warning/[0.07] px-3 py-2 text-[12.5px] text-text-secondary">
            <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-status-warning" aria-hidden />
            Checked against the source: {m.revising}. Rewriting the answer from the cited text…
          </p>
        )}

        {m.warning && (
          <p className="mt-3 flex items-center gap-2 text-[12.5px] text-status-warning">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden /> {m.warning}
          </p>
        )}

        {m.error && (
          <p role="alert" className="mt-3 flex items-start gap-2 text-[13px] text-status-error">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden /> {m.error}
          </p>
        )}

        {verdict && state !== "not_found" && (
          <div className="mt-3 border-t border-border pt-3">
            <button
              type="button"
              onClick={() => setShowClaims((s) => !s)}
              aria-expanded={showClaims}
              className="flex w-full items-center gap-2 text-left"
            >
              {state === "answered" ? (
                <ShieldCheck className="h-4 w-4 shrink-0 text-status-success" aria-hidden />
              ) : (
                <ShieldAlert className="h-4 w-4 shrink-0 text-status-warning" aria-hidden />
              )}
              <span className={cn("font-mono text-micro uppercase tracking-widest", state === "answered" ? "text-status-success" : "text-status-warning")}>
                {headline}
              </span>
              <ChevronDown className={cn("ml-auto h-3.5 w-3.5 text-text-muted transition-transform", showClaims && "rotate-180")} aria-hidden />
            </button>

            {showClaims && (
              <ul className="mt-2.5 space-y-1.5">
                {verdict.claims.map((c, i) => (
                  <li key={i} className="flex items-start gap-2 text-[12.5px] leading-snug">
                    {c.status === "supported" ? (
                      <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-status-success" aria-label="supported" />
                    ) : (
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-status-warning" aria-label="to check" />
                    )}
                    <span className="text-text-secondary">
                      {c.text}
                      {c.sources.length > 0 && (
                        <span className="ml-1 font-mono text-micro text-text-dim">[{c.sources.join(", ")}]</span>
                      )}
                      {c.issues.map((issue) => (
                        <span key={issue} className="block font-mono text-micro text-status-warning">{issue}</span>
                      ))}
                    </span>
                  </li>
                ))}
                <li className="pt-1 font-mono text-micro leading-relaxed text-text-dim">
                  Amounts, rates and quotations are matched to the cited text exactly. Whether a paraphrase is
                  faithful is for you to judge from the source.
                </li>
              </ul>
            )}
          </div>
        )}

        {(finished || m.retrievalConfidence !== undefined) && !m.error && (
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-micro text-text-dim">
            {m.exactMatch ? (
              <span className="inline-flex items-center gap-1 text-status-success">
                <Target className="h-3 w-3" aria-hidden /> exact section match
              </span>
            ) : m.retrievalConfidence !== undefined ? (
              <span>retrieval {Math.round(m.retrievalConfidence * 100)}%</span>
            ) : null}
            {modelLine && (
              <span
                className="inline-flex items-center gap-1"
                title={m.backendUsed?.reason ? `Fell back because: ${m.backendUsed.reason}` : undefined}
              >
                {m.backendUsed?.backend === "groq" ? <Cloud className="h-3 w-3" aria-hidden /> : <Cpu className="h-3 w-3" aria-hidden />}
                {modelLine}
              </span>
            )}
            {m.revised && <span>rewritten after checking</span>}
            {total && (
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3 w-3" aria-hidden /> {total}
              </span>
            )}
          </div>
        )}
      </div>

      {primary.length > 0 && (
        <div className="mt-2.5">
          <p className="mb-1.5 font-mono text-micro uppercase tracking-widest text-text-muted">
            {state === "not_found" ? "Closest passages" : finished ? "Cited" : "Sources"}
          </p>
          <div className="grid gap-2">
            {primary.map((c) => (
              <CitationCard
                key={c.index}
                citation={c}
                cited={citedOnly ? true : undefined}
                open={openCards.has(c.index)}
                onToggle={() => toggleCard(c.index)}
              />
            ))}
          </div>
        </div>
      )}

      {others.length > 0 && (
        <div className="mt-2.5">
          <button
            type="button"
            onClick={() => setShowOthers((s) => !s)}
            aria-expanded={showOthers}
            className="flex items-center gap-1.5 font-mono text-micro uppercase tracking-widest text-text-muted hover:text-text-primary"
          >
            <ChevronDown className={cn("h-3 w-3 transition-transform", showOthers && "rotate-180")} aria-hidden />
            Also retrieved ({others.length})
          </button>
          {showOthers && (
            <div className="mt-1.5 grid gap-2">
              {others.map((c) => (
                <CitationCard
                  key={c.index}
                  citation={c}
                  cited={false}
                  open={openCards.has(c.index)}
                  onToggle={() => toggleCard(c.index)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {followUps.length > 0 && onFollowUp && (
        <div className="mt-3 flex flex-wrap gap-2">
          {followUps.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => onFollowUp(q)}
              className="rounded-full border border-border px-3 py-1 text-[12.5px] text-text-secondary transition-colors hover:border-signal/50 hover:text-text-primary"
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
