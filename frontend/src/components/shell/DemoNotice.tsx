"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Info, X } from "lucide-react";
import { API_BASE as API } from "@/lib/api";

const KEY = "prism-demo-notice-closed";

/**
 * A small corner note on the hosted demo, which runs without a language model: it says what is
 * recorded, what is switched off and where the full system lives. Shown only when the API says it
 * is a demo, never over the landing story, and closed for the rest of the session once dismissed.
 */
export default function DemoNotice() {
  const path = usePathname();
  const [demo, setDemo] = useState(false);
  const [open, setOpen] = useState(false);
  const [closed, setClosed] = useState(true);

  useEffect(() => {
    try {
      setClosed(sessionStorage.getItem(KEY) === "1");
    } catch {
      setClosed(false);
    }
    fetch(`${API}/health`)
      .then((r) => (r.ok ? r.json() : null))
      .then((h) => setDemo(!!h?.llm_backend?.demo))
      .catch(() => {});
  }, []);

  if (!demo || closed || path === "/") return null;

  const close = () => {
    setClosed(true);
    try {
      sessionStorage.setItem(KEY, "1");
    } catch {
      /* the note simply returns next visit */
    }
  };

  return (
    <aside
      aria-label="About this hosted demo"
      className="fixed bottom-4 left-4 z-40 max-w-[min(24rem,calc(100vw-2rem))] rounded-[6px] border border-border-light bg-bg-elevated text-[13px] text-text-secondary shadow-lift"
    >
      <div className="flex items-center gap-2 px-3 py-2">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="flex flex-1 items-center gap-2 text-left text-text-primary"
        >
          <Info className="h-4 w-4 shrink-0 text-signal" aria-hidden />
          <span>Hosted demo: no language model runs here</span>
        </button>
        <button type="button" onClick={close} aria-label="Dismiss this note" className="rounded p-1 text-text-muted hover:text-text-primary">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      {open && (
        <div className="space-y-2 border-t border-border px-3 py-3 leading-relaxed">
          <p>
            Ask replays answers recorded from the full system for common questions and, for anything else, quotes the best-matching
            provisions. Everything else (the parsed statutes, comparisons, the policy sandbox, the research results, provenance and
            explanations) is computed live.
          </p>
          <p>Uploads and new language-model analyses are switched off. The full system runs locally or with Docker.</p>
          <a
            href="https://github.com/febinrenu/PRISM"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block underline underline-offset-4 hover:text-text-primary"
          >
            Source and setup on GitHub
          </a>
        </div>
      )}
    </aside>
  );
}
