/**
 * The story's text. Every figure is read from the snapshot (data.ts); none is
 * typed here. scripts/check-story-literals.mjs fails the lint if one is.
 */
import Link from "next/link";
import { ArrowDown, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { SYSTEM_LABEL, inr, lakh, millions, pct, story } from "./data";
import { CurveFigure, DecileFigure, FaultBars, FieldList, ProvisionCard, VerdictTable } from "./figures";
import { Act, Kicker, Num, SourceRef, Step, Val } from "./ui";
import CurtainLink from "./CurtainLink";

const f = story.focus;
const sysLabel = SYSTEM_LABEL[f.system];
const cells = story.matrix.cells;
const assembledCells = cells.filter((c) => c.status === "assembled");
const totalFlips = assembledCells.reduce((s, c) => s + (c.flips ?? 0), 0);
const biggest = story.matrix.systems.reduce((a, b) => (b.params_b > a.params_b ? b : a));
const assembledBy = (id: string) => cells.filter((c) => c.system === id && c.status === "assembled").length;
const smallModels = story.matrix.systems.filter((s) => s.kind.startsWith("small"));
const smallAssembled = smallModels.reduce((s, m) => s + assembledBy(m.id), 0);
const ita = story.corpus.statutes.find((s) => s.key.startsWith("ITA2025/amended"));
const itaSet = cells.filter((c) => c.set === "ITA2025_new_act");
const itaAssembled = itaSet.filter((c) => c.status === "assembled").length;
const gap = story.curve.largest_gap;
const sobol = Object.entries(story.behaviour.sobol_total).sort((a, b) => b[1] - a[1]);
const penaltyRank = sobol.findIndex(([k]) => k === "penalty_rate");
const ORDINAL = ["most", "second most", "third most", "fourth most", "fifth most"];
const readersOfPenalty = Object.entries(story.behaviour.systems).filter(([, v]) => v.matches_expert);
const insampleDev = (
  100 * Math.max(...Object.entries(story.numbers).filter(([k]) => k.startsWith("insample@")).map(([, v]) => Math.abs(Number(v.value) - 1)))
).toFixed(1);
const strongest = story.injection.kinds[0];
const weakest = story.injection.kinds[story.injection.kinds.length - 1];

// Mobile: the copy sits at the bottom over a rising scrim. Desktop: the copy
// owns the left column, so the scrim comes in from the left.
const scrim =
  "pointer-events-none absolute inset-x-0 bottom-0 h-[70%] bg-gradient-to-t from-ink via-ink/85 to-transparent lg:inset-y-0 lg:left-0 lg:right-auto lg:h-full lg:w-[58%] lg:bg-gradient-to-r lg:from-ink/95 lg:via-ink/60";

function Body({ className, children }: { className?: string; children: React.ReactNode }) {
  return <p className={cn("max-w-[34rem] text-[16px] leading-[1.7] text-text-secondary sm:text-[17px]", className)}>{children}</p>;
}

function H2({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <h2 id={id} className="max-w-[18ch] font-serif text-[clamp(2.4rem,5.6vw,4.6rem)] leading-[0.98] tracking-[-0.02em] text-text-primary">
      {children}
    </h2>
  );
}

/* ── Prologue ───────────────────────────────────────────────────────────── */

export function Prologue() {
  return (
    <Act id="prologue" index={0} length={1.7} label="Prologue">
      <div className={scrim} />
      <div className="relative flex h-full flex-col justify-end px-5 pb-[12vh] sm:px-10 lg:px-16">
        <div data-at={-1} className="mb-6 font-mono text-micro uppercase tracking-[0.22em] text-text-muted">
          PRISM · <span className="text-signal">tax law, read by machine, checked against the law</span>
        </div>
        <h1 className="story-title max-w-[15ch] font-serif text-display text-text-primary">
          A law is a program nobody&nbsp;runs.
        </h1>
        <div className="mt-8 flex flex-col gap-8 md:flex-row md:items-end md:justify-between">
          <Body className="story-lede">
            Every year India rewrites its income tax by amending text. Language models can now read that text and turn it
            into numbers. We tested whether the numbers they read lead to the same policy conclusions as the law itself, and
            traced every difference back to a clause.
          </Body>
          <div className="story-lede flex flex-wrap gap-3">
            <a
              href="#text"
              className="inline-flex h-11 items-center gap-2 rounded-[4px] bg-signal px-5 text-[15px] font-medium text-ink transition-colors hover:bg-signal-soft"
            >
              Read the experiment <ArrowDown className="h-4 w-4" />
            </a>
            <CurtainLink
              href="/research"
              className="inline-flex h-11 items-center gap-2 rounded-[4px] border border-border-light px-5 text-[15px] text-text-primary transition-colors hover:border-glow"
            >
              See the results <ArrowUpRight className="h-4 w-4" />
            </CurtainLink>
          </div>
        </div>
      </div>
      <div className="scroll-cue absolute bottom-5 left-1/2 hidden -translate-x-1/2 font-mono text-micro uppercase tracking-[0.2em] text-text-dim sm:block">
        scroll
      </div>
    </Act>
  );
}

/* ── I · The text ───────────────────────────────────────────────────────── */

export function ActText() {
  return (
    <Act id="text" index={1} length={2.4} label="One: the text">
      <div className={scrim} />
      <div className="relative flex h-full flex-col justify-end px-5 pb-[10vh] sm:px-10 lg:px-16">
        <Step at={0.02}>
          <Kicker numeral="I">The text</Kicker>
        </Step>
        <Step at={0.05}>
          <H2 id="text-h">The tax code is rewritten in prose.</H2>
        </Step>
        <Step at={0.22} className="mt-6">
          <Body>
            This corpus holds{" "}
            <Val source={story.corpus.source}>{inr(story.corpus.sections_total)} sections</Val> across{" "}
            {story.corpus.statutes.length} statutes, parsed down to every clause and proviso with exact character offsets.
          </Body>
        </Step>
        <Step at={0.55} className="mt-4">
          <Body>
            Section 20 of the Finance Act 2025 raises the income-tax rebate. It never states the new rule. It swaps words
            inside the old one.
          </Body>
        </Step>
      </div>
      <ProvisionCard className="fig-static mx-5 mb-10 sm:mx-10 lg:mx-16" />
    </Act>
  );
}

/* ── II · Reading ───────────────────────────────────────────────────────── */

export function ActReading() {
  return (
    <Act id="reading" index={2} length={2.6} label="Two: reading">
      <div className={scrim} />
      <div className="relative flex h-full flex-col justify-end px-5 pb-[8vh] sm:px-10 lg:px-16">
        <Step at={0.02}>
          <Kicker numeral="II">Reading</Kicker>
        </Step>
        <Step at={0.05}>
          <H2 id="reading-h">A model reads it and fills in a form.</H2>
        </Step>
        <Step at={0.3} className="mt-6">
          <Body>
            {sysLabel} read section 20 and returned a rebate: income up to ₹{inr(f.extracted.max_income)}, at most ₹
            {inr(f.extracted.max_rebate)}. Both are right, and each points to the words it came from.
            <SourceRef source={f.source} label="the extraction" />
          </Body>
        </Step>
        <Step at={0.62} className="mt-4">
          <Body>
            <span className="text-signal">It missed the third change.</span> Clause (b) is the marginal relief, which
            stops someone just over the limit from paying more tax than their income above it. The amendment only changes
            its numbers, so the words &ldquo;marginal relief&rdquo; never appear.
          </Body>
        </Step>
      </div>
      <FieldList className="fig-static mx-5 mb-10 max-w-xl sm:mx-10 lg:mx-16" />
    </Act>
  );
}

/* ── III · The curve ────────────────────────────────────────────────────── */

export function ActCurve() {
  return (
    <Act id="curve" index={3} length={2.5} label="Three: the tax curve">
      <div className="pointer-events-none absolute inset-y-0 left-0 w-[60%] bg-gradient-to-r from-ink/90 via-ink/50 to-transparent" />
      <div className="relative flex h-full flex-col justify-end px-5 pb-[10vh] sm:px-10 lg:justify-center lg:px-16 lg:pb-0">
        <Step at={0.02}>
          <Kicker numeral="III">The tax curve</Kicker>
        </Step>
        <Step at={0.05}>
          <H2 id="curve-h">One missed clause tears the curve.</H2>
        </Step>
        <Step at={0.2} className="mt-6">
          <Body>
            Tax on a salary under the new regime for AY {story.deciles.ay}, computed by the same engine from the expert
            coding of the law and from the model&apos;s reading.
          </Body>
        </Step>
        <Step at={0.58} className="mt-6">
          <div className="grid max-w-md grid-cols-2 gap-px overflow-hidden rounded-[6px] border border-border-light bg-border">
            <div className="col-span-2 bg-ink/90 px-4 py-2.5 font-mono text-micro uppercase tracking-[0.14em] text-text-muted">
              A salary of ₹{lakh(gap.salary)}
            </div>
            <div className="bg-ink/90 px-4 py-3">
              <div className="text-[12px] text-text-muted">The law asks</div>
              <div className="font-serif text-[2.2rem] leading-none text-text-primary">
                <Val source={story.curve.source}>₹{inr(gap.expert)}</Val>
              </div>
            </div>
            <div className="bg-ink/90 px-4 py-3">
              <div className="text-[12px] text-text-muted">The model&apos;s reading asks</div>
              <div className="font-serif text-[2.2rem] leading-none text-signal">₹{inr(gap.system)}</div>
            </div>
          </div>
        </Step>
      </div>
      <CurveFigure className="fig-static mx-5 mb-10 max-w-2xl sm:mx-10 lg:mx-16" />
    </Act>
  );
}

/* ── IV · Society ───────────────────────────────────────────────────────── */

export function ActSociety() {
  return (
    <Act id="society" index={4} length={2.9} label="Four: the population">
      <div className={scrim} />
      <div className="relative flex h-full flex-col justify-end px-5 pb-[8vh] sm:px-10 lg:px-16">
        <Step at={0.02}>
          <Kicker numeral="IV">The population</Kicker>
        </Step>
        <Step at={0.05}>
          <H2 id="society-h">
            Run the law on <Val source={story.population.source}>{millions(story.population.returns_total)}</Val> returns.
          </H2>
        </Step>
        <Step at={0.25} className="mt-6">
          <Body>
            Each point stands for a group of taxpayers, built from the income-tax department&apos;s count of returns by
            income range. They settle by income; the lines mark tenths of the population.
          </Body>
        </Step>
        <Step at={0.5} className="mt-4">
          <Body>
            <span className="text-status-info">Blue</span> points pay less under the AY {story.deciles.ay} law than under
            the year before.
          </Body>
        </Step>
        <Step at={0.72} className="mt-4">
          <Body>
            Under the model&apos;s reading,{" "}
            <Val source={f.source} className="text-signal">
              {millions(f.taxpayers_with_different_tax)} returns
            </Val>{" "}
            would be taxed differently, and the revenue cost of the reform would be off by{" "}
            <Val source={f.source}>₹{inr(f.revenue_error_crore)} crore</Val>.
          </Body>
        </Step>
      </div>
      <DecileFigure className="fig-static mx-5 mb-10 max-w-2xl sm:mx-10 lg:mx-16" />
    </Act>
  );
}

/* ── V · The verdict ────────────────────────────────────────────────────── */

export function ActVerdict() {
  return (
    <Act id="verdict" index={5} length={2.6} label="Five: the verdict">
      <div className="pointer-events-none absolute inset-y-0 right-0 w-[55%] bg-gradient-to-l from-ink/95 via-ink/70 to-transparent max-lg:hidden" />
      <div className={cn(scrim, "lg:hidden")} />
      <div className="relative flex h-full flex-col justify-end px-5 pb-[8vh] sm:px-10 lg:ml-auto lg:max-w-[40rem] lg:justify-center lg:px-16 lg:pb-0">
        <Step at={0.02}>
          <Kicker numeral="V">
            <Num k="reforms" /> reforms · <Num k="systems" /> readers
          </Kicker>
        </Step>
        <Step at={0.05}>
          <H2 id="verdict-h">But the conclusions hold.</H2>
        </Step>
        <Step at={0.15} className="mt-6">
          <Body>
            Despite the torn curve, the same deciles gain, the cut stays progressive and revenue still falls:{" "}
            <Val source={f.source}>
              {f.flips} of {f.conclusions}
            </Val>{" "}
            pre-registered conclusions flip.
          </Body>
        </Step>
        <Step at={0.4} className="mt-4">
          <Body>
            We ran {story.matrix.reforms.length} income-tax reforms, from the Finance Act 2020 to the Income-tax Act 2025,
            through readers ranging from a {biggest.params_b}-billion-parameter model to hand-written rules. A reading counts only if it assembles into a
            complete schedule; otherwise it gives no conclusion.
          </Body>
        </Step>
        <Step at={0.72} className="mt-4">
          <Body>
            Across all {assembledCells.length} readings that assembled, {totalFlips} conclusions flipped. The largest
            revenue error was ₹<Num k={`maxreverr@${f.system}`} /> crore. The small local models assembled{" "}
            {smallAssembled === 0 ? "none" : smallAssembled} of the {story.matrix.reforms.length * smallModels.length}{" "}
            readings they attempted.
          </Body>
        </Step>
      </div>
      <VerdictTable className="fig-static mx-5 mb-10 sm:mx-10 lg:mx-16" />
    </Act>
  );
}

/* ── VI · Faults ────────────────────────────────────────────────────────── */

export function ActFaults() {
  return (
    <Act id="faults" index={6} length={2.4} label="Six: breaking the law on purpose">
      <div className={scrim} />
      <div className="relative flex h-full flex-col justify-end px-5 pb-[8vh] sm:px-10 lg:px-16">
        <Step at={0.02}>
          <Kicker numeral="VI">Breaking the law on purpose</Kicker>
        </Step>
        <Step at={0.05}>
          <H2 id="faults-h">Which mistakes matter?</H2>
        </Step>
        <Step at={0.25} className="mt-6">
          <Body>
            We injected <Num k="injections" /> typed errors into the expert law, the kinds of slip a reader makes.{" "}
            <Num k="injectionsflipping" /> of them flipped at least one conclusion.
          </Body>
        </Step>
        <Step at={0.6} className="mt-4">
          <Body>
            <span className="text-signal">{strongest ? labelOf(strongest.error) : ""}</span> flipped up to{" "}
            <Num k={`injflipmax@${strongest?.error}`} suffix="%" /> of them.{" "}
            {weakest ? labelOf(weakest.error) : ""} flipped <Num k={`injflipmax@${weakest?.error}`} suffix="%" />. Removing
            a rule changes conclusions; blurring a number mostly does not.
          </Body>
        </Step>
      </div>
      <FaultBars className="fig-static mx-5 mb-10 max-w-2xl sm:mx-10 lg:mx-16" />
    </Act>
  );
}

function labelOf(e: string) {
  const map: Record<string, string> = {
    drop_rebate: "Dropping the rebate",
    off_by_one_rupee: "A bound off by one rupee",
  };
  return map[e] ?? e.replace(/_/g, " ");
}

/* ── VII · Provenance ───────────────────────────────────────────────────── */

export function ActProvenance() {
  return (
    <Act id="provenance" index={7} length={2.7} label="Seven: provenance">
      <div className={scrim} />
      <div className="relative flex h-full flex-col justify-end px-5 pb-[8vh] sm:px-10 lg:px-16">
        <Step at={0.02}>
          <Kicker numeral="VII">Provenance</Kicker>
        </Step>
        <Step at={0.05}>
          <H2 id="provenance-h">Every number traces back to its words.</H2>
        </Step>
        <Step at={0.25} className="mt-6">
          <Body>
            The Income-tax Act 2025 replaces the 1961 Act. Parsed, it has{" "}
            {ita ? (
              <Val source={story.corpus.source}>
                {ita.chapters} chapters and {ita.sections} sections
              </Val>
            ) : null}
            . Each extracted value keeps the span it came from, so an error in revenue is attributed to the clause that
            caused it.
          </Body>
        </Step>
        <Step at={0.6} className="mt-4">
          <Body>
            In the new Act the rebate lives in <span className="text-signal">section 156</span>.{" "}
            {itaAssembled === 0
              ? "No reader assembled it: each found the right amounts, then attached them to both tax regimes at once, which the law does not do."
              : `${itaAssembled} of ${itaSet.length} readers assembled it.`}
          </Body>
        </Step>
      </div>
      <nav aria-label="Provenance of the focus error" className="fig-static mx-5 mb-10 sm:mx-10 lg:mx-16">
        <ul role="tree" className="space-y-1 font-mono text-[13px] text-text-secondary">
          <li role="treeitem" aria-expanded="true" aria-selected="false">
            Revenue error · ₹{inr(f.revenue_error_crore)} crore
            <ul role="group" className="ml-5 mt-1 space-y-1 border-l border-border pl-3">
              <li role="treeitem" aria-expanded="true" aria-selected="false">
                Parameter · {f.param_diff.join(", ")}
                <ul role="group" className="ml-5 mt-1 border-l border-border pl-3">
                  <li role="treeitem" aria-selected="false">
                    Provision · {f.provision} (section 87A of the 1961 Act)
                  </li>
                </ul>
              </li>
            </ul>
          </li>
        </ul>
      </nav>
    </Act>
  );
}

/* ── VIII · Limits (a paper page, no canvas) ───────────────────────────── */

export function ActLimits() {
  const others = Object.keys(story.behaviour.systems).length - readersOfPenalty.length;
  const items = [
    {
      title: "Behaviour",
      body: (
        <>
          In an agent-based model of compliance, the share of tax evaded settles near <Num k="bhgapmedian" /> (between{" "}
          <Num k="bhgapfive" /> and <Num k="bhgapninetyfive" /> across parameter draws). Reading the{" "}
          {pct(story.behaviour.expert_penalty)} penalty as {pct(story.behaviour.misread_penalty)} raises it by{" "}
          <Num k="bhdiffmean" /> on average. The penalty rate is the {ORDINAL[penaltyRank] ?? "an important"} important input.{" "}
          {readersOfPenalty.length} readers found the penalty correctly; {others} found none.
        </>
      ),
    },
    {
      title: "Explanations",
      body: (
        <>
          The words a model cites as its evidence are no more faithful than random words: the ERASER comprehensiveness of
          gpt-oss-120b&apos;s cited spans is <Num k="faithcomprehensiveness@gpt-oss-120b@dev" />, and of random spans of the
          same length <Num k="faithrandomcomprehensiveness@gpt-oss-120b@dev" />.
        </>
      ),
    },
    {
      title: "Retrieval",
      body: (
        <>
          The question-answering view retrieves the right section with a recall at five of{" "}
          <Num k="ragrfive@hybrid-minilm+rerank" /> across <Num k="ragqueries" /> questions, and separates unanswerable
          ones with an AUROC of <Num k="ragauroc@hybrid-minilm+rerank" />.
        </>
      ),
    },
    {
      title: "Forecasting",
      body: (
        <>
          In sample, the population model lands within{" "}
          <Val source={{ file: "paper/tables/numbers.tex", key: "insample@*" }}>{insampleDev}%</Val> of reported tax. Its
          forecast from{" "}
          <span className="whitespace-nowrap">2022-23</span> to <span className="whitespace-nowrap">2023-24</span> scored
          worse than simply carrying the last year forward (skill <Num k="skill@2022-23to2023-24" />
          ).
        </>
      ),
    },
    {
      title: "The sandbox",
      body: (
        <>
          The app&apos;s agent-based policy simulator is illustrative. Its parameters are partly assumed, it is labelled as a
          sandbox wherever it appears, and none of the results above use it.
        </>
      ),
    },
  ];
  return (
    <section id="limits" data-act={8} aria-labelledby="limits-h" className="act-flow surface-paper relative z-10">
      <div className="mx-auto max-w-6xl px-5 py-24 sm:px-10 sm:py-32 lg:px-16">
        <div className="mb-5 flex items-center gap-3 font-mono text-micro uppercase tracking-[0.2em] text-ink/60">
          <span className="text-signal-ink">VIII</span>
          <span className="h-px w-8 bg-ink/20" aria-hidden />
          <span>What this does not show</span>
        </div>
        <h2 id="limits-h" className="max-w-[16ch] font-serif text-[clamp(2.4rem,5.6vw,4.6rem)] leading-[0.98] tracking-[-0.02em] text-ink">
          The parts we can&apos;t claim.
        </h2>
        <div className="mt-14 grid gap-x-12 gap-y-10 md:grid-cols-2">
          {items.map((it, i) => (
            <article key={it.title} className={cn("border-t border-ink/15 pt-5", i === 0 && "md:col-span-2 md:max-w-3xl")}>
              <h3 className="font-mono text-micro uppercase tracking-[0.16em] text-signal-ink">{it.title}</h3>
              <p className="mt-3 text-[16px] leading-[1.7] text-ink/80 [&_button]:text-ink">{it.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Finale ─────────────────────────────────────────────────────────────── */

export function Finale() {
  const links = [
    { href: "/research", title: "The results", body: "Every run, every reform, inspectable down to the quoted span." },
    { href: "/statutes", title: "The statutes", body: "Read the parsed Acts by chapter, section and proviso." },
    { href: "/start", title: "Analyse a PDF", body: "Upload a statute, or open the demo, and work through it." },
    { href: "/chat", title: "Ask the corpus", body: "Questions answered from the statutes, with citations." },
  ];
  return (
    <Act id="finale" index={9} length={1.9} label="Finale">
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[60%] bg-gradient-to-t from-ink via-ink/80 to-transparent" />
      <div className="relative flex h-full flex-col justify-end px-5 pb-[8vh] sm:px-10 lg:px-16">
        <Step at={0.35}>
          <h2 id="finale-h" className="max-w-[16ch] font-serif text-[clamp(2.6rem,7vw,6rem)] leading-[0.95] tracking-[-0.025em] text-text-primary">
            Read the law. Then check the <em className="text-signal">reading</em>.
          </h2>
        </Step>
        <Step at={0.5} className="mt-10 grid gap-px overflow-hidden rounded-[6px] border border-border-light bg-border sm:grid-cols-2 lg:grid-cols-4">
          {links.map((l) => (
            <CurtainLink
              key={l.href}
              href={l.href}
              className="group flex flex-col justify-between gap-6 bg-ink/90 p-5 transition-colors hover:bg-ink-800"
            >
              <span className="flex items-center justify-between text-[17px] text-text-primary">
                {l.title}
                <ArrowUpRight className="h-4 w-4 text-text-muted transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-signal" />
              </span>
              <span className="text-[13px] leading-relaxed text-text-muted">{l.body}</span>
            </CurtainLink>
          ))}
        </Step>
        <Step at={0.6} className="mt-6 text-[13px] text-text-dim">
          <Link href="https://github.com/febinrenu/PRISM" className="underline underline-offset-4 hover:text-text-secondary">
            Source code, data and paper
          </Link>
        </Step>
      </div>
    </Act>
  );
}
