"use client";

import { useState } from "react";
import { BookOpen, ExternalLink, Copy, Check } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const ENDPOINTS: { method: string; path: string; desc: string }[] = [
  { method: "POST", path: "/v1/documents/upload", desc: "Upload a PDF, returns doc_id" },
  { method: "POST", path: "/v1/analyze/{doc_id}", desc: "Run the full analysis (blocking), returns stats" },
  { method: "GET", path: "/v1/documents/{doc_id}", desc: "Document status + metadata" },
  { method: "GET", path: "/v1/clauses/{doc_id}", desc: "All extracted clauses" },
  { method: "GET", path: "/v1/causal/{doc_id}", desc: "LLM-extracted causal rules" },
  { method: "GET", path: "/v1/explain/{doc_id}/{clause_id}", desc: "LIME explanation for a clause" },
  { method: "POST", path: "/v1/simulate/{doc_id}", desc: "Run a socioeconomic simulation" },
  { method: "POST", path: "/v1/rag/query", desc: "Ask a grounded, cited question over the corpus" },
  { method: "GET", path: "/v1/corpus/documents", desc: "List corpus documents" },
];

const methodColor: Record<string, string> = {
  GET: "text-status-info",
  POST: "text-status-success",
  DELETE: "text-status-error",
};

export default function ApiDocsPage() {
  const [copied, setCopied] = useState(false);
  const curl = `curl -X POST ${API}/v1/rag/query \\
  -H "Authorization: Bearer prism_sk_..." \\
  -H "Content-Type: application/json" \\
  -d '{"question": "What are the penalties for late filing?"}'`;

  return (
    <div className="relative">

      <div className="mx-auto w-full max-w-7xl px-4 pb-10 pt-10 sm:px-6 sm:pt-14 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
          <div>
            <h1 className="font-serif text-headline text-text-primary flex items-center gap-3">
              <BookOpen className="w-5 h-5 text-accent-primary" /> Public API
            </h1>
            <p className="font-mono text-micro uppercase tracking-widest text-text-muted mt-1">
              REST · Bearer API key · 100 req/hour free tier
            </p>
          </div>
          <a
            href={`${API}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 font-mono text-micro uppercase tracking-widest px-3 py-2 rounded-sm text-text-inverse bg-accent-primary"
          >
            <ExternalLink className="w-3 h-3" /> Interactive Swagger UI
          </a>
        </div>

        {/* Auth */}
        <div className="glass-card p-6 mb-6">
          <h3 className="font-display text-sm mb-3">Authentication</h3>
          <p className="text-[13px] text-text-secondary leading-relaxed mb-3">
            Every request needs your API key (find it on your{" "}
            <a href="/dashboard" className="text-accent-primary hover:text-accent-bright">Dashboard</a>) as a bearer token:
          </p>
          <div className="rounded-md border border-border bg-bg-surface p-3 flex items-center justify-between gap-2">
            <code className="font-mono text-micro text-text-secondary">Authorization: Bearer prism_sk_...</code>
          </div>
        </div>

        {/* Example */}
        <div className="glass-card p-6 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display text-sm">Example — RAG query</h3>
            <button
              onClick={() => {
                navigator.clipboard.writeText(curl);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className="inline-flex items-center gap-1.5 font-mono text-micro uppercase tracking-widest text-text-muted hover:text-text-primary transition-colors"
            >
              {copied ? <Check className="w-3 h-3 text-status-success" /> : <Copy className="w-3 h-3" />}
              Copy
            </button>
          </div>
          <pre className="rounded-md border border-border bg-bg-deep p-4 overflow-x-auto">
            <code className="font-mono text-micro text-text-secondary whitespace-pre">{curl}</code>
          </pre>
        </div>

        {/* Endpoint reference */}
        <div className="glass-card p-6">
          <h3 className="font-display text-sm mb-4">Endpoints</h3>
          <ul className="flex flex-col divide-y divide-border">
            {ENDPOINTS.map((e) => (
              <li key={e.path} className="flex items-center gap-4 py-3">
                <span className={`font-mono text-micro font-bold w-12 shrink-0 ${methodColor[e.method]}`}>
                  {e.method}
                </span>
                <code className="font-mono text-micro text-text-primary shrink-0">{e.path}</code>
                <span className="text-[12px] text-text-muted ml-auto text-right">{e.desc}</span>
              </li>
            ))}
          </ul>
          <p className="mt-4 font-mono text-micro text-text-dim">
            Rate limit: 100 requests/hour per API key. Responses are JSON. Full schemas in the Swagger UI.
          </p>
        </div>
      </div>
    </div>
  );
}
