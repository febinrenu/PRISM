"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowLeft, LayoutDashboard, MessageSquare, Network, ShieldEllipsis, BookOpen, LogOut } from "lucide-react";
import PrismMark from "@/components/brand/PrismMark";
import { useAuth } from "@/lib/auth";

const LINKS = [
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/corpus", label: "Corpus", icon: Network },
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/api-docs", label: "API", icon: BookOpen },
];

/** Shared header for the Phase 3 authenticated pages. */
export default function TopNav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <nav className="relative z-20 px-6 py-4 border-b border-border flex items-center justify-between">
      <div className="flex items-center gap-4">
        <Link href="/" className="flex items-center gap-2 text-text-muted hover:text-text-primary transition-colors">
          <ArrowLeft className="w-4 h-4" />
          <PrismMark size={28} />
        </Link>
        <div className="hidden md:flex items-center gap-1">
          {LINKS.map((l) => {
            const Icon = l.icon;
            const active = pathname === l.href;
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest px-3 py-1.5 rounded-sm transition-colors ${
                  active ? "text-accent-primary bg-accent-primary/10" : "text-text-muted hover:text-text-primary"
                }`}
              >
                <Icon className="w-3 h-3" /> {l.label}
              </Link>
            );
          })}
          {user?.role === "admin" && (
            <Link
              href="/admin"
              className={`flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest px-3 py-1.5 rounded-sm transition-colors ${
                pathname === "/admin" ? "text-accent-primary bg-accent-primary/10" : "text-text-muted hover:text-text-primary"
              }`}
            >
              <ShieldEllipsis className="w-3 h-3" /> Admin
            </Link>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3">
        {user ? (
          <>
            <span className="hidden sm:block font-mono text-[10px] text-text-muted">{user.email}</span>
            <button
              onClick={logout}
              className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest px-2.5 py-1.5 rounded-sm border border-border text-text-muted hover:text-text-primary hover:border-light transition-colors"
            >
              <LogOut className="w-3 h-3" /> Sign out
            </button>
          </>
        ) : (
          <Link
            href="/login"
            className="font-mono text-[10px] uppercase tracking-widest px-3 py-1.5 rounded-sm text-text-inverse bg-accent-primary"
          >
            Sign in
          </Link>
        )}
      </div>
    </nav>
  );
}
