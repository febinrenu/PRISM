"use client";

import { Fragment, useMemo } from "react";
import { splitAnswer } from "@/components/chat/answerParts";

const NONE: never[] = []; // a stable default, so the memo below holds

/** An answer with its [Source N] markers drawn as small buttons that open the
 *  source they point at, and any amount or rate the verifier could not find in
 *  the cited text underlined, so a flagged figure is visible where it is stated. */
export default function AnswerText({
  text,
  unsupported = NONE,
  invalid = NONE,
  onCite,
  streaming,
}: {
  text: string;
  unsupported?: string[];
  invalid?: number[];
  onCite: (n: number) => void;
  streaming?: boolean;
}) {
  const parts = useMemo(() => splitAnswer(text, unsupported), [text, unsupported]);

  return (
    <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-text-primary">
      {parts.map((p, i) => {
        if (p.kind === "text") return <Fragment key={i}>{p.value}</Fragment>;
        if (p.kind === "flag") {
          return (
            <span
              key={i}
              className="underline decoration-status-warning decoration-wavy underline-offset-4"
              title="This amount or rate is not in the text the sentence cites"
            >
              {p.value}
            </span>
          );
        }
        return (
          <Fragment key={i}>
            {p.nums!.map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => onCite(n)}
                aria-label={`Open source ${n}`}
                className={
                  invalid.includes(n)
                    ? "mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[3px] bg-status-error/15 px-1 align-baseline font-mono text-[11px] text-status-error line-through"
                    : "mx-0.5 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[3px] bg-signal/15 px-1 align-baseline font-mono text-[11px] text-signal transition-colors hover:bg-signal/30"
                }
              >
                {n}
              </button>
            ))}
          </Fragment>
        );
      })}
      {streaming && <span className="ml-0.5 animate-pulse text-signal">▊</span>}
    </p>
  );
}
