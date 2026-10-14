"use client";

/**
 * The story's words. Every figure is read from the snapshot (data.ts); none
 * is typed here (scripts/check-story-literals.mjs fails the lint if one is).
 */
import Link from "next/link";
import { ArrowDown, ArrowUpRight } from "lucide-react";
import { tokens } from "@/design/tokens";
import { cn } from "@/lib/utils";
import { ENTITY_ORDER, ERROR_LABEL, RISK_ORDER, SYSTEM_LABEL, inr, lakh, millions, pct, story } from "../data";
import { CurveFigure, DecileFigure, FaultBars, FieldList, ProvisionCard, VerdictTable } from "../figures";
import { Num, PNum, SourceRef, Val } from "../ui";
import CurtainLink from "../CurtainLink";
import { ActSection, Beat, Body, Chip, Count, Headline, Kicker, Stat, step } from "./kit";
import { Marquee } from "./Marquee";

const f = story.focus;
const sysLabel = SYSTEM_LABEL[f.system];
const cells = story.matrix.cells;
const assembled = cells.filter((c) => c.status === "assembled");
const totalFlips = assembled.reduce((s, c) => s + (c.flips ?? 0), 0);
const biggest = story.matrix.systems.reduce((a, b) => (b.params_b > a.params_b ? b : a));
const smallModels = story.matrix.systems.filter((s) => s.kind.startsWith("small"));
const smallAssembled = assembled.filter((c) => smallModels.some((m) => m.id === c.system)).length;
const gap = story.curve.largest_gap;
const strongest = story.injection.kinds[0];
const weakest = story.injection.kinds[story.injection.kinds.length - 1];
const sobol = Object.entries(story.behaviour.sobol_total).sort((a, b) => b[1] - a[1]);
const penaltyRank = sobol.findIndex(([k]) => k === "penalty_rate");
const ORDINAL = ["most", "second most", "third most", "fourth most", "fifth most"];
const readersOfPenalty = Object.entries(story.behaviour.systems).filter(([, v]) => v.matches_expert);
const insampleDev = (
  100 * Math.max(...Object.entries(story.numbers).filter(([k]) => k.startsWith("insample@")).map(([, v]) => Math.abs(Number(v.value) - 1)))
).toFixed(1);
const chat = story.chat;
const firstRight = chat.citations.find((c) => c.relevant);
const DEMO = "/analyze/demo_income_tax_2025";
const entityColor = (l: string) => tokens.entity[l as keyof typeof tokens.entity].base;

const btn = "inline-flex h-12 items-center gap-2 rounded-[4px] px-5 text-[15px] font-medium transition-[background-color,border-color,transform] duration-300";

/* ── Prologue ───────────────────────────────────────────────────────────── */

function Hero() {
  return (
    <ActSection id="hero" label="PRISM">
      <Beat from={-9} to={0.42} className="max-w-[60rem] pb-[2vh] lg:pb-[6vh] lg:self-end">
        <Kicker>PRISM · legal intelligence for Indian tax law</Kicker>
        <Headline as="h1" id="hero-h" className="max-w-[12ch]">
          A law is a program nobody&nbsp;runs.
        </Headline>
        <Body className="max-w-[34rem]">
          PRISM reads tax statutes clause by clause, ties every number to the words it came from, runs the law on the
          population it governs, and checks the reading against the law itself.
        </Body>
        <div data-rise="" className="mt-9 flex flex-wrap items-center gap-3">
          <CurtainLink href={DEMO} data-magnetic="" className={cn(btn, "bg-signal text-ink hover:bg-signal-soft")}>
            Open the demo <ArrowUpRight className="h-4 w-4" />
          </CurtainLink>
          <a href="#why" data-magnetic="" className={cn(btn, "border border-border-light text-text-primary hover:border-glow")}>
            Read the story <ArrowDown className="h-4 w-4" />
          </a>
        </div>
      </Beat>
      <Beat from={0.46} to={1.1} className="self-end lg:self-center">
        <Kicker>White light in, six kinds of meaning out</Kicker>
        <Headline id="hero-split">Every clause does something.</Headline>
        <Body>
          It obliges, penalises, grants a right, sets a threshold, names an actor or a beneficiary. PRISM separates them
          the way a prism separates light. In the Income-tax Bill, 2025:
        </Body>
        <div className="mt-6 flex flex-wrap gap-2">
          {ENTITY_ORDER.map((l) => (
            <Chip key={l} color={entityColor(l)}>
              <span className="capitalize">{l.toLowerCase()}</span>
              <span className="font-mono text-[12px] text-text-primary">
                <PNum k={`entity@${l}`} />
              </span>
            </Chip>
          ))}
        </div>
      </Beat>
    </ActSection>
  );
}

/* ── I · Why ────────────────────────────────────────────────────────────── */

function Why() {
  const statutes = story.corpus.statutes.length;
  return (
    <ActSection id="why" label="One: why" overlay={<Marquee items={story.pipeline.headings} />}>
      <Beat from={0.04} to={0.33}>
        <Kicker n="I">Why it is needed</Kicker>
        <Headline id="why-h">The law is written in prose.</Headline>
        <div className="mt-9 grid max-w-[30rem] grid-cols-2 gap-8">
          <Stat value={<Count>{inr(story.corpus.sections_total)}</Count>} source={<SourceRef source={story.corpus.source} label="sections" />} label="sections in this corpus" />
          <Stat value={<Count>{String(statutes)}</Count>} label="Acts, from the Income-tax Act to the Finance Acts" />
        </div>
        <Body>Each stack here is one of them, as tall as its sections; point at one to open it. Parliament amends them every year.</Body>
      </Beat>
      <Beat from={0.36} to={0.63}>
        <Kicker n="I">Why it is needed</Kicker>
        <Headline>Nobody runs it.</Headline>
        <Body>
          To know what a budget does to a salary, someone has to turn sentences back into numbers: slabs, rebates,
          thresholds, reliefs. By hand, for every rule, every year. And amendments rarely restate a rule. They swap words
          inside the old one.
        </Body>
      </Beat>
      <Beat from={0.66} to={0.97}>
        <Kicker n="I">Why it is needed</Kicker>
        <Headline>Machines can read it now. Can the reading be trusted?</Headline>
        <Body>
          Language models will happily fill in the numbers. PRISM asks the question that matters: do the numbers they
          read lead to the same conclusions as the law? When they don&apos;t, which clause is to blame?
        </Body>
      </Beat>
    </ActSection>
  );
}

/* ── II · Reading ───────────────────────────────────────────────────────── */

function Read() {
  return (
    <ActSection id="read" label="Two: how PRISM reads a statute">
      <Beat from={-0.02} to={0.195}>
        <Kicker n="II">How PRISM reads · {step(1)} Ingest</Kicker>
        <Headline id="read-h">Every page, every character.</Headline>
        <div className="mt-8 flex gap-10">
          <Stat value={<PNum k="pages" />} label="pages in the Income-tax Bill, 2025" />
        </div>
        <Body>
          The PDF becomes text with exact character offsets and its place on the page, so anything PRISM extracts can be
          traced back to the words that say it.
        </Body>
      </Beat>
      <Beat from={0.205} to={0.395}>
        <Kicker n="II">How PRISM reads · {step(2)} Segment</Kicker>
        <Headline>Structure, not paragraphs.</Headline>
        <Body>
          A statute is cut the way lawyers cite it: chapter, section, sub-section, clause, proviso. The tree here is the
          consolidated Income-tax Act 2025; the bright branch is the rebate.
        </Body>
        <div className="mt-8">
          <Stat value={<PNum k="clauses" />} label="clauses in the demo Act" />
        </div>
      </Beat>
      <Beat from={0.405} to={0.595}>
        <Kicker n="II">How PRISM reads · {step(3)} Tag</Kicker>
        <Headline>Six kinds of meaning.</Headline>
        <Body>
          Each clause is tagged for who must act, what they must do, what they may claim, what it costs them and where
          the lines are drawn. The prism passes over the clause and the tags light up.
        </Body>
        <div className="mt-6 flex flex-wrap gap-2">
          {ENTITY_ORDER.map((l) => (
            <Chip key={l} color={entityColor(l)}>
              <span className="capitalize">{l.toLowerCase()}</span>
            </Chip>
          ))}
        </div>
        <div className="mt-7">
          <Stat value={<PNum k="entities" />} label="tagged entities" />
        </div>
      </Beat>
      <Beat from={0.605} to={0.795}>
        <Kicker n="II">How PRISM reads · {step(4)} Cause → effect</Kicker>
        <Headline>If this, then that.</Headline>
        <Body>
          Conditions are linked to their consequences and rated by risk: a missed condition behind a penalty matters more
          than one behind a definition. Behind the clause, every pattern in the Act.
        </Body>
        <div className="mt-8 grid grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
          {RISK_ORDER.map((r) => (
            <Stat key={r} value={<PNum k={`risk@${r}`} />} label={r.toLowerCase()} />
          ))}
        </div>
      </Beat>
      <Beat from={0.805} to={1.05}>
        <Kicker n="II">How PRISM reads · {step(5)} Provenance</Kicker>
        <Headline>Every number keeps its clause.</Headline>
        <Body>
          Document, chapter, clause, pattern, entity: one graph, so any figure PRISM produces can be walked back to its
          words. Point at a clause in the web to open it.
        </Body>
        <div className="mt-8 flex gap-10">
          <Stat value={<PNum k="nodes" />} label="nodes" />
          <Stat value={<PNum k="edges" />} label="edges" />
        </div>
        <div data-rise="" className="mt-8">
          <CurtainLink href="/provenance/demo_income_tax_2025" data-magnetic="" className="inline-flex items-center gap-2 text-[15px] text-text-primary underline decoration-border-light underline-offset-[6px] hover:decoration-signal">
            Open the provenance graph <ArrowUpRight className="h-4 w-4" />
          </CurtainLink>
        </div>
      </Beat>
    </ActSection>
  );
}

/* ── III · Running ──────────────────────────────────────────────────────── */

function Run() {
  return (
    <ActSection id="run" label="Three: running the law">
      <Beat from={-0.02} to={0.325}>
        <Kicker n="III">What it runs · {step(6)} Simulate</Kicker>
        <Headline id="run-h">Run the law on a country.</Headline>
        <Body>
          Each point is a group of taxpayers, built from the income-tax department&apos;s count of returns by income range.
          The lines mark tenths of the population; <span style={{ color: tokens.hue.teal.text }}>teal</span> points pay less under
          the AY {story.deciles.ay} law than under the year before.
        </Body>
        <div className="mt-8">
          <Stat value={<Val source={story.population.source}>{millions(story.population.returns_total)}</Val>} label="returns, simulated as weighted groups" />
        </div>
      </Beat>
      <Beat from={0.335} to={0.645}>
        <Kicker n="III">What it runs · {step(7)} The schedule</Kicker>
        <Headline>Tax, salary by salary.</Headline>
        <Body>
          The same engine turns the coded law into a schedule: what every salary pays under the new regime for AY{" "}
          {story.deciles.ay}. The dim line is the year before.
          <SourceRef source={story.curve.source} label="the tax curve" />
        </Body>
      </Beat>
      <Beat from={0.655} to={1.1}>
        <Kicker n="III">What it runs · {step(8)} Ask</Kicker>
        <Headline>Ask the statutes.</Headline>
        <Body>
          Questions are answered from the corpus, with the sections that answer them. One benchmark question, &ldquo;
          {chat.query}&rdquo;: {firstRight ? `the right section, s.${firstRight.number}, comes back at rank ${firstRight.rank}.` : "the right section is not in the top five."}
          <SourceRef source={chat.source} label="this retrieval" />
        </Body>
        <div className="mt-8 grid max-w-[30rem] grid-cols-2 gap-8">
          <Stat value={<Num k="ragrfive@hybrid-minilm+rerank" />} label="recall at five across the benchmark" />
          <Stat value={<Num k="ragqueries" />} label="benchmark questions" />
        </div>
        <div data-rise="" className="mt-8">
          <CurtainLink href="/chat" data-magnetic="" className="inline-flex items-center gap-2 text-[15px] text-text-primary underline decoration-border-light underline-offset-[6px] hover:decoration-signal">
            Ask the corpus <ArrowUpRight className="h-4 w-4" />
          </CurtainLink>
        </div>
      </Beat>
    </ActSection>
  );
}

/* ── IV · One clause ────────────────────────────────────────────────────── */

function Case() {
  return (
    <ActSection id="case" label="Four: one clause">
      <Beat from={-0.02} to={0.5}>
        <Kicker n="IV">The proof · one clause</Kicker>
        <Headline id="case-h">Then a model reads the amendment.</Headline>
        <Body>
          Section 20 of the Finance Act 2025 raises the rebate by swapping words inside section 87A. {sysLabel} read it:
          income up to ₹{inr(f.extracted.max_income)}, a rebate of at most ₹{inr(f.extracted.max_rebate)}.
          <SourceRef source={f.source} label="the extraction" />
        </Body>
        <ul data-rise="" className="mt-7 max-w-[30rem] divide-y divide-border border-y border-border text-[15px]">
          <li className="flex items-center justify-between py-3">
            <span className="text-text-secondary">Income limit</span>
            <span className="font-mono text-text-primary">₹{inr(f.extracted.max_income)} ✓</span>
          </li>
          <li className="flex items-center justify-between py-3">
            <span className="text-text-secondary">Rebate</span>
            <span className="font-mono text-text-primary">₹{inr(f.extracted.max_rebate)} ✓</span>
          </li>
          <li className="flex items-center justify-between py-3">
            <span className="text-signal">Marginal relief</span>
            <span className="font-mono text-signal">missed ✕</span>
          </li>
        </ul>
        <Body className="text-[15px]">
          Clause (b) is the marginal relief. The amendment only changes its numbers, so the words never appear on the page.
        </Body>
      </Beat>
      <Beat from={0.52} to={1.1}>
        <Kicker n="IV">The proof · one clause</Kicker>
        <Headline>One missed clause tears the curve.</Headline>
        <div className="mt-9 grid max-w-[32rem] grid-cols-2 gap-8">
          <Stat value={<Val source={story.curve.source}>₹{inr(gap.expert)}</Val>} label={`the law, on ₹${lakh(gap.salary)}`} />
          <Stat value={`₹${inr(gap.system)}`} tone="signal" label="the model's reading" />
        </div>
        <Body>
          Across the population,{" "}
          <Val source={f.source} className="text-signal">
            {millions(f.taxpayers_with_different_tax)} returns
          </Val>{" "}
          would be taxed differently, and the reform&apos;s revenue cost would be off by{" "}
          <Val source={f.source}>₹{inr(f.revenue_error_crore)} crore</Val>.
        </Body>
      </Beat>
    </ActSection>
  );
}

/* ── V · Verdict ────────────────────────────────────────────────────────── */

function Verdict() {
  const readings = story.matrix.reforms.length * smallModels.length;
  return (
    <ActSection id="verdict" label="Five: the verdict" side="right">
      <Beat from={0.02} to={0.5}>
        <Kicker n="V">The verdict</Kicker>
        <Headline id="verdict-h">But do the conclusions survive?</Headline>
        <Body>
          <Num k="reforms" /> income-tax reforms, from the Finance Act 2020 to the Income-tax Act 2025, read by <Num k="systems" />{" "}
          readers, from a {biggest.params_b}-billion-parameter model to hand-written rules. A reading counts only if it
          assembles into a complete schedule.
        </Body>
        <ul data-rise="" className="mt-7 space-y-2.5 text-[14px] text-text-secondary">
          <li className="flex items-center gap-3">
            <span className="h-3 w-5 rounded-[2px] bg-paper" aria-hidden /> assembled, no conclusion flipped
          </li>
          <li className="flex items-center gap-3">
            <span className="h-3 w-5 rounded-[2px] bg-signal" aria-hidden /> assembled, a conclusion flipped
          </li>
          <li className="flex items-center gap-3">
            <span className="h-3 w-5 rounded-[2px] bg-ink-600" aria-hidden /> did not assemble: no conclusion
          </li>
        </ul>
      </Beat>
      <Beat from={0.52} to={1.1}>
        <Kicker n="V">The verdict</Kicker>
        <Headline>
          {totalFlips === 0 ? "Not one conclusion flipped." : `${totalFlips} conclusions flipped.`}
        </Headline>
        <div className="mt-9 grid max-w-[32rem] grid-cols-2 gap-8">
          <Stat value={<Count>{String(assembled.length)}</Count>} label="readings assembled" />
          <Stat value={<Num k={`maxreverr@${f.system}`} />} label="crore, the largest revenue error" />
        </div>
        <Body>
          The torn curve did not change the policy story: the same deciles gain, the cut stays progressive. The small
          local models assembled {smallAssembled === 0 ? "none" : smallAssembled} of the {readings} readings they
          attempted. Point at a tile to see its run.
        </Body>
      </Beat>
    </ActSection>
  );
}

/* ── VI · Faults ────────────────────────────────────────────────────────── */

function Faults() {
  return (
    <ActSection id="faults" label="Six: breaking the law on purpose">
      <Beat from={0.02} to={0.5}>
        <Kicker n="VI">Faults</Kicker>
        <Headline id="faults-h">We broke the law on purpose.</Headline>
        <div className="mt-9 grid max-w-[30rem] grid-cols-2 gap-8">
          <Stat value={<Num k="injections" />} label="typed errors injected into the expert law" />
          <Stat value={<Num k="injectionsflipping" />} tone="signal" label="flipped at least one conclusion" />
        </div>
        <Body>The kinds of slip a reader makes: a dropped slab, last year&apos;s table, a lakh read as a crore.</Body>
      </Beat>
      <Beat from={0.52} to={1.1}>
        <Kicker n="VI">Faults</Kicker>
        <Headline>Dropping a rule matters. Blurring a number mostly doesn&apos;t.</Headline>
        <Body>
          <span className="text-signal">{strongest ? ERROR_LABEL[strongest.error] ?? strongest.error : ""}</span> flipped up to{" "}
          <Num k={`injflipmax@${strongest?.error}`} suffix="%" /> of conclusions.{" "}
          {weakest ? ERROR_LABEL[weakest.error] ?? weakest.error : ""} flipped <Num k={`injflipmax@${weakest?.error}`} suffix="%" />.
          Each column is one kind of error; each spark, one injection. Point at a column for its numbers.
        </Body>
      </Beat>
    </ActSection>
  );
}

/* ── VII · Limits ───────────────────────────────────────────────────────── */

function Limits() {
  const others = Object.keys(story.behaviour.systems).length - readersOfPenalty.length;
  const items = [
    {
      title: "Behaviour",
      body: (
        <>
          In an agent-based model of compliance, the share of tax evaded settles near <Num k="bhgapmedian" />. Reading the{" "}
          {pct(story.behaviour.expert_penalty)} penalty as {pct(story.behaviour.misread_penalty)} raises it by <Num k="bhdiffmean" />{" "}
          on average; the penalty rate is the {ORDINAL[penaltyRank] ?? "an"} important input. {readersOfPenalty.length} readers
          found the penalty; {others} found none.
        </>
      ),
    },
    {
      title: "Explanations",
      body: (
        <>
          The words a model cites as evidence are no more faithful than random words: comprehensiveness{" "}
          <Num k="faithcomprehensiveness@gpt-oss-120b@dev" /> for its spans, <Num k="faithrandomcomprehensiveness@gpt-oss-120b@dev" /> for
          random ones.
        </>
      ),
    },
    {
      title: "Retrieval",
      body: (
        <>
          Recall at five of <Num k="ragrfive@hybrid-minilm+rerank" /> over <Num k="ragqueries" /> questions; unanswerable ones
          separate with an AUROC of <Num k="ragauroc@hybrid-minilm+rerank" />.
        </>
      ),
    },
    {
      title: "Forecasting",
      body: (
        <>
          In sample the population model lands within <Val source={{ file: "paper/tables/numbers.tex", key: "insample@*" }}>{insampleDev}%</Val> of
          reported tax, but its forecast to <span className="whitespace-nowrap">2023-24</span> scored worse than carrying the last
          year forward (skill <Num k="skill@2022-23to2023-24" />).
        </>
      ),
    },
    {
      title: "The sandbox",
      body: <>The app&apos;s agent-based policy simulator is illustrative, labelled as a sandbox, and none of the results above use it.</>,
    },
  ];
  return (
    <ActSection id="limits" label="Seven: what this does not show" side="center">
      <Beat from={0.06} to={1.1} className="text-left">
        <Kicker n="VII" className="justify-center">
          What we can&apos;t claim
        </Kicker>
        <Headline id="limits-h" className="mx-auto max-w-[18ch] text-center">
          The honest part.
        </Headline>
        <div className="mt-12 grid gap-px overflow-hidden rounded-[6px] border border-border bg-border sm:grid-cols-2 lg:grid-cols-5">
          {items.map((it) => (
            <article key={it.title} data-rise="" className="bg-ink/85 p-5 backdrop-blur-sm">
              <h3 className="font-mono text-micro uppercase tracking-[0.16em] text-text-muted">{it.title}</h3>
              <p className="mt-3 text-[14px] leading-[1.6] text-text-secondary">{it.body}</p>
            </article>
          ))}
        </div>
      </Beat>
    </ActSection>
  );
}

/* ── Finale ─────────────────────────────────────────────────────────────── */

function End() {
  const links = [
    { href: DEMO, title: "Open the demo", body: "The Income-tax Bill, 2025, segmented, tagged and linked to its pages." },
    { href: "/start", title: "Analyse a statute", body: "Upload a PDF and work through it clause by clause." },
    { href: "/research", title: "The results", body: "Every reform and reader, down to the quoted span." },
    { href: "/statutes", title: "The statutes", body: "The parsed Acts by chapter, section and proviso." },
    { href: "/chat", title: "Ask the corpus", body: "Questions answered from the statutes, with citations." },
  ];
  return (
    <ActSection id="end" label="Begin" side="center">
      <Beat from={0.28} to={9} className="text-left">
        <Headline id="end-h" className="mx-auto max-w-[14ch] text-center text-[clamp(2.8rem,7vw,6.4rem)] leading-[0.94]">
          Read the law. Then check the <em className="text-signal">reading</em>.
        </Headline>
        <div className="mt-12 grid gap-px overflow-hidden rounded-[6px] border border-border-light bg-border sm:grid-cols-2 lg:grid-cols-5">
          {links.map((l, i) => (
            <CurtainLink
              key={l.href}
              href={l.href}
              data-rise=""
              data-magnetic=""
              className={cn("group flex min-h-[9.5rem] flex-col justify-between gap-6 bg-ink/85 p-5 backdrop-blur-sm transition-colors hover:bg-ink-800", i === 0 && "bg-ink-800")}
            >
              <span className="flex items-center justify-between text-[17px] text-text-primary">
                {l.title}
                <ArrowUpRight className="h-4 w-4 text-text-muted transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-signal" />
              </span>
              <span className="text-[13px] leading-relaxed text-text-muted">{l.body}</span>
            </CurtainLink>
          ))}
        </div>
        <div data-rise="" className="mt-7 text-center text-[13px] text-text-dim">
          <Link href="https://github.com/febinrenu/PRISM" className="underline underline-offset-4 hover:text-text-secondary">
            Source code, data and paper
          </Link>
        </div>
      </Beat>
    </ActSection>
  );
}

export function StoryActs() {
  return (
    <>
      <Hero />
      <Why />
      <Read />
      <Run />
      <Case />
      <Verdict />
      <Faults />
      <Limits />
      <End />
    </>
  );
}

/** The figures the canvas draws, as DOM: visible on tier 0, read by screen readers otherwise. */
export function StaticFigures() {
  return (
    <div className="fig-static-wrap mx-auto grid max-w-6xl gap-10 px-5 py-16 sm:px-10 lg:px-16">
      <ProvisionCard />
      <FieldList />
      <CurveFigure />
      <DecileFigure />
      <VerdictTable />
      <FaultBars />
      <p className="text-[13px] text-text-dim">
        Pipeline counts are from the demo document: <PNum k="pages" /> pages, <PNum k="clauses" /> clauses, <PNum k="entities" /> entities,{" "}
        <PNum k="causal" /> cause–effect patterns. Paper numbers: <Num k="reforms" /> reforms.
      </p>
    </div>
  );
}
