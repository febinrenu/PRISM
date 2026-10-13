import type { Metadata } from "next";
import Link from "next/link";
import UploadZone from "@/components/landing/UploadZone";
import DocumentCorpus from "@/components/landing/DocumentCorpus";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";

export const metadata: Metadata = { title: "Analyse a PDF" };

const STEPS = [
  {
    title: "Structure",
    body: "The statute is parsed into chapters, sections, sub-sections, provisos, explanations and schedules, each with its exact character offsets and page position.",
  },
  {
    title: "Clauses and entities",
    body: "Each clause is tagged for obligations, penalties, rights, thresholds, actors and beneficiaries, and for condition → consequence patterns, by rules you can read.",
  },
  {
    title: "Meaning",
    body: "Clauses are embedded and projected to a map, so similar provisions sit together and can be searched by meaning.",
  },
  {
    title: "Rules, read by a model",
    body: "On request, a language model reads clauses into structured rules. Every value it returns must quote the words it came from; anything it cannot ground is dropped.",
  },
  {
    title: "Provenance",
    body: "Everything is linked in one graph from document to clause to entity and rule, so any output can be walked back to its text.",
  },
  {
    title: "Explanations",
    body: "Each extraction can be probed with LIME and attention views. These are labelled as commentary: the research found cited spans are no more faithful than random ones.",
  },
];

export default function StartPage() {
  return (
    <PageContainer>
      <PageHeader
        kicker="Analyse a document"
        title="Bring a statute. Read it clause by clause."
        lede="Upload an Act, a Bill or a Finance Act. PRISM parses its structure, tags every clause, and builds a workspace where each finding links back to the words that support it."
      />
      <div className="grid gap-12 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)] [&>*]:min-w-0">
        <section aria-labelledby="upload-h">
          <h2 id="upload-h" className="sr-only">
            Upload
          </h2>
          <UploadZone />
          <p className="mt-4 text-[13px] leading-relaxed text-text-dim">
            Uploads are kept on the analysis server. Signed in, they are listed only for you; anonymous uploads and the demo
            are shared. Model extraction runs on whichever backend the server is configured with, which may be a hosted
            service.
          </p>
        </section>
        <section aria-labelledby="recent-h">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 id="recent-h" className="font-serif text-title text-text-primary">
              Documents
            </h2>
            <Link href="/dashboard" className="text-[13px] text-text-muted underline-offset-4 hover:text-text-primary hover:underline">
              Dashboard
            </Link>
          </div>
          <DocumentCorpus />
        </section>
      </div>

      <section aria-labelledby="pipeline-h" className="mt-24">
        <div className="rule-mark mb-10">§</div>
        <h2 id="pipeline-h" className="max-w-xl font-serif text-headline text-text-primary">
          What happens to a PDF
        </h2>
        <ol className="mt-10 grid gap-px overflow-hidden rounded-[8px] border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.title} className="flex flex-col gap-3 bg-bg-base p-6">
              <span className="font-mono text-micro text-signal">{String(i + 1).padStart(2, "0")}</span>
              <h3 className="text-[17px] text-text-primary">{s.title}</h3>
              <p className="text-[14px] leading-relaxed text-text-muted">{s.body}</p>
            </li>
          ))}
        </ol>
        <p className="mt-8 max-w-2xl text-[14px] leading-relaxed text-text-muted">
          The research behind PRISM tests whether these readings lead to the same policy conclusions as the law.{" "}
          <Link href="/" className="text-text-primary underline decoration-border-light underline-offset-4 hover:decoration-signal">
            Read the story
          </Link>{" "}
          or{" "}
          <Link href="/research" className="text-text-primary underline decoration-border-light underline-offset-4 hover:decoration-signal">
            open the results
          </Link>
          .
        </p>
      </section>
    </PageContainer>
  );
}
