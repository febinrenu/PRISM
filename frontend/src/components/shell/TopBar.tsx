"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import ThemeToggle from "./ThemeToggle";
import { usePathname } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import * as Menu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, LogOut, Menu as MenuIcon, Search, X } from "lucide-react";
import { Wordmark } from "@/components/brand/PrismMark";
import { Kbd } from "@/components/ui/kit";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useCommandPalette } from "./CommandPalette";
import { ROUTES, isActive } from "./routes";

/** The one top bar for every app route. */
export default function TopBar({ className }: { className?: string }) {
  const pathname = usePathname() ?? "/";
  const { user, logout } = useAuth();
  const palette = useCommandPalette();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mac, setMac] = useState(true);

  useEffect(() => setMac(/Mac|iPhone|iPad/.test(navigator.platform)), []);
  useEffect(() => setMobileOpen(false), [pathname]);

  const visible = ROUTES.filter((r) => !r.adminOnly || user?.role === "admin");
  const primary = visible.filter((r) => r.slot === "primary");
  const more = visible.filter((r) => r.slot === "more");
  const moreActive = more.some((r) => isActive(pathname, r.href));

  return (
    <header
      className={cn(
        "sticky top-0 z-nav border-b border-border bg-bg-base/80 backdrop-blur-xl supports-[backdrop-filter]:bg-bg-base/65",
        className
      )}
    >
      <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-4 px-4 sm:px-6">
        <Link href="/" className="shrink-0 text-text-primary" aria-label="PRISM, back to the story">
          <Wordmark />
        </Link>

        <nav aria-label="Main" className="ml-4 hidden items-center gap-0.5 lg:flex">
          {primary.map((r) => {
            const active = isActive(pathname, r.href);
            return (
              <Link
                key={r.href}
                href={r.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative rounded-[4px] px-3 py-1.5 text-[13.5px] transition-colors",
                  active ? "text-text-primary" : "text-text-muted hover:text-text-primary"
                )}
              >
                {r.label}
                {active && <span aria-hidden className="absolute inset-x-3 -bottom-[11px] h-[2px] bg-signal" />}
              </Link>
            );
          })}
          <Menu.Root>
            <Menu.Trigger
              className={cn(
                "inline-flex items-center gap-1 rounded-[4px] px-3 py-1.5 text-[13.5px] outline-none transition-colors",
                moreActive ? "text-text-primary" : "text-text-muted hover:text-text-primary"
              )}
            >
              More <ChevronDown className="h-3.5 w-3.5" aria-hidden />
            </Menu.Trigger>
            <Menu.Portal>
              <Menu.Content
                align="start"
                sideOffset={10}
                className="z-overlay min-w-[260px] rounded-md border border-border-light bg-bg-surface p-1.5 shadow-lift"
              >
                {more.map((r) => (
                  <Menu.Item key={r.href} asChild>
                    <Link
                      href={r.href}
                      className="flex items-start gap-3 rounded-[4px] px-3 py-2 outline-none data-[highlighted]:bg-bg-elevated"
                    >
                      <r.icon className="mt-0.5 h-4 w-4 text-text-muted" aria-hidden />
                      <span>
                        <span className="block text-[14px] text-text-primary">{r.label}</span>
                        <span className="block text-[12px] text-text-dim">{r.hint}</span>
                      </span>
                    </Link>
                  </Menu.Item>
                ))}
              </Menu.Content>
            </Menu.Portal>
          </Menu.Root>
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle className="hidden sm:inline-flex" />
          <button
            type="button"
            onClick={palette.open}
            aria-label="Go to a page or action"
            title={`Go to… (${mac ? "⌘" : "Ctrl"} K)`}
            className="hidden h-9 items-center gap-2 rounded-[4px] border border-border bg-bg-surface px-2.5 text-[13px] text-text-muted transition-colors hover:border-border-light hover:text-text-secondary md:inline-flex xl:px-3"
          >
            <Search className="h-3.5 w-3.5" aria-hidden />
            {/* the full label only where the main nav leaves room for it */}
            <span className="hidden items-center gap-2 xl:inline-flex" aria-hidden>
              <span className="pr-6">Go to…</span>
              <Kbd>{mac ? "⌘" : "Ctrl"}</Kbd>
              <Kbd>K</Kbd>
            </span>
          </button>
          <Link
            href="/start"
            className="hidden h-9 items-center rounded-[4px] bg-signal px-3.5 text-[13px] font-medium text-ink transition-colors hover:bg-signal-soft sm:inline-flex"
          >
            Analyse a PDF
          </Link>
          {user ? (
            <Menu.Root>
              <Menu.Trigger
                aria-label="Account"
                className="flex h-9 w-9 items-center justify-center rounded-[4px] border border-border bg-bg-elevated font-mono text-[13px] uppercase text-text-secondary outline-none hover:border-border-light"
              >
                {(user.name || user.email || "?").slice(0, 1)}
              </Menu.Trigger>
              <Menu.Portal>
                <Menu.Content
                  align="end"
                  sideOffset={10}
                  className="z-overlay min-w-[220px] rounded-md border border-border-light bg-bg-surface p-1.5 shadow-lift"
                >
                  <div className="px-3 py-2 text-[12px] text-text-dim">{user.email}</div>
                  <Menu.Item
                    onSelect={logout}
                    className="flex cursor-pointer items-center gap-2 rounded-[4px] px-3 py-2 text-[14px] text-text-secondary outline-none data-[highlighted]:bg-bg-elevated data-[highlighted]:text-text-primary"
                  >
                    <LogOut className="h-4 w-4" aria-hidden /> Sign out
                  </Menu.Item>
                </Menu.Content>
              </Menu.Portal>
            </Menu.Root>
          ) : (
            <Link
              href="/login"
              className="hidden h-9 items-center rounded-[4px] border border-border-light px-3 text-[13px] text-text-secondary hover:border-glow hover:text-text-primary sm:inline-flex"
            >
              Sign in
            </Link>
          )}

          <Dialog.Root open={mobileOpen} onOpenChange={setMobileOpen}>
            <Dialog.Trigger
              aria-label="Open menu"
              className="flex h-9 w-9 items-center justify-center rounded-[4px] border border-border text-text-secondary lg:hidden"
            >
              <MenuIcon className="h-4 w-4" />
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-modal bg-ink-950/70 backdrop-blur-sm" />
              <Dialog.Content
                aria-describedby={undefined}
                className="fixed inset-y-0 right-0 z-modal flex w-[min(360px,100vw)] flex-col border-l border-border-light bg-bg-surface p-5 shadow-lift"
              >
                <div className="mb-6 flex items-center justify-between">
                  <Dialog.Title className="font-serif text-2xl text-text-primary">Menu</Dialog.Title>
                  <Dialog.Close aria-label="Close menu" className="flex h-9 w-9 items-center justify-center rounded-[4px] border border-border">
                    <X className="h-4 w-4" />
                  </Dialog.Close>
                </div>
                <nav aria-label="Mobile" className="flex flex-col gap-0.5 overflow-y-auto">
                  <Link href="/" className="rounded-[4px] px-3 py-2.5 text-[15px] text-text-secondary hover:bg-bg-elevated">
                    The story
                  </Link>
                  {visible.map((r) => {
                    const active = isActive(pathname, r.href);
                    return (
                      <Link
                        key={r.href}
                        href={r.href}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "flex items-center gap-3 rounded-[4px] px-3 py-2.5 text-[15px]",
                          active ? "bg-bg-elevated text-text-primary" : "text-text-secondary hover:bg-bg-elevated"
                        )}
                      >
                        <r.icon className={cn("h-4 w-4", active ? "text-signal" : "text-text-muted")} aria-hidden />
                        {r.label}
                      </Link>
                    );
                  })}
                </nav>
                <div className="mt-auto flex flex-col items-start gap-4 border-t border-border pt-4">
                  <ThemeToggle withLabel />
                  {user ? (
                    <button type="button" onClick={logout} className="flex items-center gap-2 text-[14px] text-text-secondary">
                      <LogOut className="h-4 w-4" /> Sign out ({user.email})
                    </button>
                  ) : (
                    <Link href="/login" className="text-[14px] text-text-secondary underline underline-offset-4">
                      Sign in
                    </Link>
                  )}
                </div>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </div>
      </div>
    </header>
  );
}
