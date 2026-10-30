"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import DocContextBar from "@/components/shell/DocContextBar";
import { Callout, SandboxTag, Tag } from "@/components/ui/kit";
import DynamicsMode from "@/components/simulate/DynamicsMode";
import LawMode from "@/components/policy/LawMode";
import { useDocumentStore } from "@/hooks/useDocumentStore";

type Mode = "law" | "dynamics";

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "law", label: "Statute mode", hint: "Change the law's own rate table and price it" },
  { id: "dynamics", label: "Clause dynamics", hint: "Agents respond to the rules extracted from this document" },
];

export default function SimulatePage({ params }: { params: { docId: string } }) {
  const { docId } = params;
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const prefilterClause = searchParams.get("clause");
  // a link to one clause (from the clause cards) opens the dynamics mode that can use it
  const mode: Mode = searchParams.get("mode") === "dynamics" || prefilterClause ? "dynamics" : "law";
  const filename = useDocumentStore((s) => (s.docId === docId ? s.filename : null));

  const setMode = useCallback(
    (next: Mode) => {
      const q = new URLSearchParams(searchParams.toString());
      q.set("mode", next);
      if (next === "law") q.delete("clause");
      router.replace(`${pathname}?${q.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams]
  );

  return (
    <div>
      <DocContextBar docId={docId} filename={filename} view="simulate" status={mode === "dynamics" ? <SandboxTag /> : <Tag tone="ok">Statutory calculator</Tag>} />

      <div className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
        <header className="pb-2 pt-4">
          <div className="kicker mb-3">Policy sandbox</div>
          {mode === "law" ? (
            <>
              <h1 className="max-w-3xl font-serif text-headline text-text-primary">Change the law and see who pays</h1>
              <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-text-secondary">
                The rate table is read from this document. Change a rate, a limit, the rebate or the standard deduction, and
                the same calculator and taxpayer population that reproduce the published tax statistics show who pays more,
                who pays less, and what it does to revenue, with the range the data cannot narrow.
              </p>
              <Callout tone="info" className="mt-6 max-w-3xl" title="Checked against published numbers">
                Resident individuals’ income-tax, one year, static. How closely it reproduces the tax actually paid, and where it
                does not, is under <span className="text-text-primary">How far to trust it</span> below.
              </Callout>
            </>
          ) : (
            <>
              <h1 className="max-w-3xl font-serif text-headline text-text-primary">Try the rules on a synthetic society</h1>
              <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-text-secondary">
                Five groups of agents respond to the rules extracted from this document, month by month: compliance, burden and
                inequality unfold as the run streams.
              </p>
            </>
          )}
        </header>

        <div role="tablist" aria-label="Sandbox mode" className="inline-flex overflow-hidden rounded-[4px] border border-border-light">
          {MODES.map((m) => (
            <button
              key={m.id}
              role="tab"
              type="button"
              aria-selected={mode === m.id}
              title={m.hint}
              onClick={() => setMode(m.id)}
              className={cn(
                "px-4 py-2 text-[13.5px] transition-colors",
                mode === m.id ? "bg-contrast text-on-contrast" : "text-text-muted hover:text-text-primary"
              )}
            >
              {m.label}
            </button>
          ))}
        </div>

        {mode === "law" ? <LawMode docId={docId} onSwitch={() => setMode("dynamics")} /> : <DynamicsMode docId={docId} prefilterClause={prefilterClause} />}
      </div>
    </div>
  );
}
