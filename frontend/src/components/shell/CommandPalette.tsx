"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import { Command } from "cmdk";
import { Contrast, CornerDownLeft, FileText, Network, ScrollText, Search } from "lucide-react";
import { setTheme } from "@/design/theme";
import { api, getJSON } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { DocumentMeta } from "@/types";
import { ROUTES } from "./routes";

interface Statute {
  key: string;
  title: string;
  sections: number;
}

const PaletteContext = createContext<{ open: () => void }>({ open: () => {} });
export const useCommandPalette = () => useContext(PaletteContext);

/**
 * ⌘K / Ctrl+K: jump to any route, any document you can see, or any statute.
 * Documents and statutes are fetched when the palette first opens.
 */
export function CommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [docs, setDocs] = useState<DocumentMeta[] | null>(null);
  const [statutes, setStatutes] = useState<Statute[] | null>(null);
  const router = useRouter();
  const { user } = useAuth();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) return;
    if (docs === null) api.listDocuments().then((d) => setDocs(d.documents)).catch(() => setDocs([]));
    if (statutes === null)
      getJSON<{ statutes: Statute[] }>("/api/corpus/statutes")
        .then((d) => setStatutes(d.statutes))
        .catch(() => setStatutes([]));
  }, [open, docs, statutes]);

  const go = useCallback(
    (href: string) => {
      setOpen(false);
      router.push(href);
    },
    [router]
  );

  const ctx = useMemo(() => ({ open: () => setOpen(true) }), []);
  const routes = ROUTES.filter((r) => !r.adminOnly || user?.role === "admin");

  return (
    <PaletteContext.Provider value={ctx}>
      {children}
      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-modal bg-ink-950/70 backdrop-blur-sm data-[state=open]:animate-fade-up" />
          <Dialog.Content
            className="fixed left-1/2 top-[12vh] z-modal w-[calc(100vw-32px)] max-w-xl -translate-x-1/2 overflow-hidden rounded-lg border border-border-light bg-bg-surface shadow-lift"
            aria-describedby={undefined}
          >
            <Dialog.Title className="sr-only">Go to</Dialog.Title>
            <Command label="Go to" loop className="flex max-h-[70vh] flex-col">
              <div className="flex items-center gap-3 border-b border-border px-4">
                <Search className="h-4 w-4 text-text-muted" aria-hidden />
                <Command.Input
                  autoFocus
                  placeholder="Go to a page, document or statute…"
                  className="h-12 flex-1 bg-transparent text-[15px] text-text-primary placeholder:text-text-dim focus:outline-none"
                />
              </div>
              <Command.List className="scroll-thin overflow-y-auto p-2">
                <Command.Empty className="px-3 py-8 text-center text-[13px] text-text-muted">Nothing matches.</Command.Empty>
                <Group heading="Appearance">
                  <Item
                    value="theme light dark appearance"
                    onSelect={() => {
                      setTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
                      setOpen(false);
                    }}
                    icon={<Contrast className="h-4 w-4" />}
                  >
                    Switch theme (light / dark)
                  </Item>
                </Group>
                <Group heading="Pages">
                  <Item value="story home landing" onSelect={() => go("/")} icon={<span className="font-serif">P</span>}>
                    The story
                    <Hint>How PRISM tests machine-read law</Hint>
                  </Item>
                  {routes.map((r) => (
                    <Item key={r.href} value={`${r.label} ${r.hint}`} onSelect={() => go(r.href)} icon={<r.icon className="h-4 w-4" />}>
                      {r.label}
                      <Hint>{r.hint}</Hint>
                    </Item>
                  ))}
                </Group>
                {docs && docs.length > 0 && (
                  <Group heading="Documents">
                    {docs.slice(0, 30).map((d) => (
                      <Item
                        key={d.doc_id}
                        value={`doc ${d.filename} ${d.doc_id}`}
                        onSelect={() => go(`/analyze/${d.doc_id}`)}
                        icon={<FileText className="h-4 w-4" />}
                      >
                        {d.filename}
                        <Hint>{d.pages} pages · open workspace</Hint>
                      </Item>
                    ))}
                    {docs.slice(0, 30).map((d) => (
                      <Item
                        key={`${d.doc_id}-prov`}
                        value={`provenance graph ${d.filename}`}
                        onSelect={() => go(`/provenance/${d.doc_id}`)}
                        icon={<Network className="h-4 w-4" />}
                      >
                        Provenance · {d.filename}
                      </Item>
                    ))}
                  </Group>
                )}
                {statutes && statutes.length > 0 && (
                  <Group heading="Statutes">
                    {statutes.map((s) => (
                      <Item
                        key={s.key}
                        value={`statute ${s.title} ${s.key}`}
                        onSelect={() => go(`/statutes?s=${encodeURIComponent(s.key)}`)}
                        icon={<ScrollText className="h-4 w-4" />}
                      >
                        {s.title}
                        <Hint>{s.sections} sections</Hint>
                      </Item>
                    ))}
                  </Group>
                )}
              </Command.List>
              <div className="flex items-center justify-between border-t border-border px-4 py-2 text-micro text-text-dim">
                <span>↑↓ to move</span>
                <span className="inline-flex items-center gap-1">
                  <CornerDownLeft className="h-3 w-3" /> to open · esc to close
                </span>
              </div>
            </Command>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </PaletteContext.Provider>
  );
}

function Group({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Command.Group
      heading={heading}
      className="mb-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:font-mono [&_[cmdk-group-heading]]:text-micro [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.14em] [&_[cmdk-group-heading]]:text-text-dim"
    >
      {children}
    </Command.Group>
  );
}

function Item({
  children,
  icon,
  value,
  onSelect,
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
  value: string;
  onSelect: () => void;
}) {
  return (
    <Command.Item
      value={value}
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-3 rounded-[4px] px-3 py-2.5 text-[14px] text-text-secondary data-[selected=true]:bg-bg-elevated data-[selected=true]:text-text-primary"
    >
      <span className="flex h-5 w-5 shrink-0 items-center justify-center text-text-muted">{icon}</span>
      <span className="flex min-w-0 flex-1 items-baseline justify-between gap-3 truncate">{children}</span>
    </Command.Item>
  );
}

function Hint({ children }: { children: React.ReactNode }) {
  return <span className="truncate text-[12px] text-text-dim">{children}</span>;
}
