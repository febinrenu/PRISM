import {
  BookOpen,
  FlaskConical,
  GitCompare,
  LayoutDashboard,
  MessageSquare,
  Network,
  PenLine,
  ScrollText,
  ShieldEllipsis,
  Upload,
  type LucideIcon,
} from "lucide-react";

export interface RouteDef {
  href: string;
  label: string;
  hint: string;
  icon: LucideIcon;
  /** primary: in the top bar; more: in the overflow menu. */
  slot: "primary" | "more";
  adminOnly?: boolean;
}

/** Every top-level destination, used by the top bar, mobile nav and ⌘K. */
export const ROUTES: RouteDef[] = [
  { href: "/research", label: "Research", hint: "Expert vs extracted rules, error injection, retrieval", icon: FlaskConical, slot: "primary" },
  { href: "/statutes", label: "Statutes", hint: "Read the parsed Acts by chapter and section", icon: ScrollText, slot: "primary" },
  { href: "/chat", label: "Ask", hint: "Questions answered from the corpus, with citations", icon: MessageSquare, slot: "primary" },
  { href: "/corpus", label: "Corpus", hint: "Every analysed document and how they relate", icon: Network, slot: "primary" },
  { href: "/compare", label: "Compare", hint: "Two statutes, clause by clause", icon: GitCompare, slot: "primary" },
  { href: "/dashboard", label: "Dashboard", hint: "Your documents and recent activity", icon: LayoutDashboard, slot: "primary" },
  { href: "/start", label: "Analyse a PDF", hint: "Upload a statute or open the demo", icon: Upload, slot: "more" },
  { href: "/annotate", label: "Annotate", hint: "Code provisions for the gold set", icon: PenLine, slot: "more" },
  { href: "/api-docs", label: "API", hint: "The public /v1 API and keys", icon: BookOpen, slot: "more" },
  { href: "/admin", label: "Admin", hint: "Users and usage", icon: ShieldEllipsis, slot: "more", adminOnly: true },
];

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}
