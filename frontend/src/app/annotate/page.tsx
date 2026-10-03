"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CheckCircle2, Circle, CircleDashed, Loader2, PenLine } from "lucide-react";
import TopNav from "@/components/nav/TopNav";
import { useAuth } from "@/lib/auth";
import { annotateApi, type SetItem, type SetSummary } from "@/lib/annotate";

const SET_HELP: Record<string, string> = {
  pilot: "30 provisions to try the guidelines on. Compare with your co-annotator afterwards and revise the guidelines before the main rounds.",
  dev: "102 provisions used while developing prompts.",
  test: "300 provisions the paper's results are reported on. Annotate them only after the pilot is settled.",
};

export default function AnnotateHome() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [sets, setSets] = useState<SetSummary[]>([]);
  const [active, setActive] = useState("pilot");
  const [items, setItems] = useState<SetItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    annotateApi.sets().then((r) => setSets(r.sets)).catch((e) => setError(String(e.message || e)));
  }, [user]);

  useEffect(() => {
    if (!user) return;
    setItems([]);
    annotateApi.items(active).then((r) => setItems(r.items)).catch((e) => setError(String(e.message || e)));
  }, [user, active]);

  if (loading || !user) {
    return (
      <main className="min-h-screen bg-bg-base flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-accent-primary" />
      </main>
    );
  }

  const nextTodo = items.find((i) => i.status !== "done");

  return (
    <main className="relative min-h-screen app-shell bg-bg-base text-text-primary">
      <TopNav />
      <div className="relative z-10 max-w-6xl mx-auto px-6 py-8">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
          <div>
            <h1 className="font-display text-2xl uppercase tracking-wider">Annotation</h1>
            <p className="text-sm text-text-muted mt-1 max-w-2xl">
              Mark every rule each provision states, quoting spans straight from the text. You see only the provision and your own
              work. Follow <span className="text-text-secondary">docs/annotation_guidelines.md</span>.
            </p>
          </div>
          {nextTodo && (
            <Link
              href={`/annotate/${nextTodo.item_id}?set=${active}`}
              className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest px-4 py-2 rounded-sm text-text-inverse bg-accent-primary"
            >
              <PenLine className="w-3.5 h-3.5" /> Continue with {nextTodo.item_id}
            </Link>
          )}
        </div>

        {error && <p className="text-sm text-status-error mb-4" role="alert">{error}</p>}

        <div className="grid sm:grid-cols-3 gap-3 mb-6" role="tablist" aria-label="Annotation sets">
          {sets.map((s) => {
            const pct = s.items ? Math.round((s.done / s.items) * 100) : 0;
            return (
              <button
                key={s.set}
                role="tab"
                aria-selected={active === s.set}
                onClick={() => setActive(s.set)}
                className={`text-left p-4 rounded-sm border transition-colors ${
                  active === s.set ? "border-accent-primary bg-bg-elevated" : "border-border bg-bg-surface hover:border-border-light"
                }`}
              >
                <div className="flex items-baseline justify-between">
                  <span className="font-display uppercase tracking-wider">{s.set}</span>
                  <span className="font-mono text-xs text-text-muted">{s.done}/{s.items} done</span>
                </div>
                <div className="h-1 bg-bg-overlay rounded-full mt-3 overflow-hidden">
                  <div className="h-full bg-accent-primary" style={{ width: `${pct}%` }} />
                </div>
                <p className="text-xs text-text-muted mt-3 leading-relaxed">{SET_HELP[s.set]}</p>
              </button>
            );
          })}
        </div>

        <div className="border border-border rounded-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-bg-surface text-text-muted font-mono text-xs uppercase tracking-wider">
              <tr>
                <th className="text-left px-3 py-2">Item</th>
                <th className="text-left px-3 py-2">Statute</th>
                <th className="text-left px-3 py-2">Provision</th>
                <th className="text-right px-3 py-2">Length</th>
                <th className="text-left px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.item_id} className="border-t border-border hover:bg-bg-surface">
                  <td className="px-3 py-2 font-mono text-xs">
                    <Link href={`/annotate/${i.item_id}?set=${active}`} className="text-accent-primary hover:underline">
                      {i.item_id}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-text-secondary">{i.statute.split("/")[0]}</td>
                  <td className="px-3 py-2 font-mono text-xs text-text-muted truncate max-w-xs">{i.path}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-text-muted">{i.chars}</td>
                  <td className="px-3 py-2">
                    <span className="inline-flex items-center gap-1.5 text-xs">
                      {i.status === "done" ? <CheckCircle2 className="w-3.5 h-3.5 text-status-success" /> :
                        i.status === "draft" ? <CircleDashed className="w-3.5 h-3.5 text-status-warning" /> :
                          <Circle className="w-3.5 h-3.5 text-text-dim" />}
                      {i.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!items.length && !error && (
            <div className="p-6 flex justify-center"><Loader2 className="w-5 h-5 animate-spin text-accent-primary" /></div>
          )}
        </div>
      </div>
    </main>
  );
}
