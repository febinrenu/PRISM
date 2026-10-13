import Link from "next/link";
import { Wordmark } from "@/components/brand/PrismMark";

const REPO = "https://github.com/febinrenu/PRISM";

export default function SiteFooter() {
  return (
    <footer className="mt-24 border-t border-border">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 py-10 sm:px-6 md:flex-row md:items-start md:justify-between lg:px-8">
        <div className="max-w-sm">
          <Wordmark className="text-text-primary" />
          <p className="mt-4 text-[13px] leading-relaxed text-text-muted">
            Tests whether machine-read statutes lead to the same policy conclusions as the law itself, and traces
            every difference back to a clause.
          </p>
        </div>
        <nav aria-label="Footer" className="grid grid-cols-2 gap-x-12 gap-y-2 text-[13px] sm:grid-cols-3">
          <Link className="text-text-secondary hover:text-text-primary" href="/">The story</Link>
          <Link className="text-text-secondary hover:text-text-primary" href="/research">Research</Link>
          <Link className="text-text-secondary hover:text-text-primary" href="/statutes">Statutes</Link>
          <Link className="text-text-secondary hover:text-text-primary" href="/start">Analyse a PDF</Link>
          <Link className="text-text-secondary hover:text-text-primary" href="/api-docs">API</Link>
          <a className="text-text-secondary hover:text-text-primary" href={REPO} target="_blank" rel="noopener noreferrer">
            Source code
          </a>
        </nav>
      </div>
    </footer>
  );
}
