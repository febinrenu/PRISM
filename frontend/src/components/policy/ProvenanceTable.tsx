"use client";

import { BadgeCheck, FileText, Scale } from "lucide-react";
import { Tag } from "@/components/ui/kit";
import type { PolicyLaw } from "@/types";

/** Where every number of the baseline law came from: the document's own table, or the expert
 *  coding of the year it belongs to, with the provision cited. */
export default function ProvenanceTable({ law }: { law: PolicyLaw }) {
  return (
    <div className="glass-card p-5">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <div className="kicker">Where the baseline law comes from</div>
        <Tag tone={law.matched_year ? "ok" : "warn"}>
          {law.source === "document"
            ? law.matched_year
              ? `table matches AY ${law.matched_year}`
              : "table matches no coded year"
            : `expert coding, AY ${law.ay}`}
        </Tag>
      </div>
      <p className="mb-4 text-[13px] leading-relaxed text-text-muted">
        {law.source === "document" && law.schedule ? (
          <>
            The slabs were read from page {law.schedule.page} of this document and checked (they start at zero, leave no gap, end
            in an open band and never fall). What a rate table cannot say comes from the expert coding of the same year, cited
            below.
          </>
        ) : (
          <>This document has no complete rate table, so the law is the expert coding of one assessment year.</>
        )}
      </p>
      {law.review.length > 0 && (
        <ul className="mb-4 space-y-1.5">
          {law.review.map((r) => (
            <li key={r} className="rounded-[4px] border border-status-warning/35 bg-status-warning/[0.06] px-3 py-2 text-[12.5px] text-text-secondary">
              {r}
            </li>
          ))}
        </ul>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-[13px]">
          <thead>
            <tr className="text-left font-mono text-micro uppercase tracking-wider text-text-dim">
              <th className="pb-2 pr-3 font-normal">Parameter</th>
              <th className="pb-2 pr-3 font-normal">Value</th>
              <th className="pb-2 font-normal">Source</th>
            </tr>
          </thead>
          <tbody>
            {law.provenance.map((p) => (
              <tr key={p.parameter} className="border-t border-border align-top">
                <td className="py-2 pr-3 text-text-primary">{p.parameter}</td>
                <td className="py-2 pr-3 text-text-secondary">{p.value}</td>
                <td className="py-2 text-text-muted">
                  <span className="inline-flex items-start gap-1.5">
                    {p.from_document ? (
                      <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-signal" aria-label="from the document" />
                    ) : (
                      <Scale className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-dim" aria-label="expert coding" />
                    )}
                    <span>
                      {p.source}
                      {p.check && (
                        <span className="mt-0.5 flex items-start gap-1.5 text-[12px] text-text-dim">
                          <BadgeCheck className="mt-0.5 h-3 w-3 shrink-0" aria-hidden /> {p.check}
                        </span>
                      )}
                    </span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 font-mono text-micro text-text-dim">
        Scope: resident individuals, income at normal rates; a static model of one year’s tax. The old regime is unchanged by a
        scenario; each taxpayer files under the regime that costs them less.
      </p>
    </div>
  );
}
