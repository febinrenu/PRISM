import Link from "next/link";
import { Wordmark } from "@/components/brand/PrismMark";

export const metadata = { title: "Not found" };

export default function NotFound() {
  return (
    <main id="main" className="relative flex min-h-dvh flex-col">
      <div className="ruled" aria-hidden />
      <div className="relative mx-auto flex w-full max-w-7xl items-center px-4 py-5 sm:px-6">
        <Link href="/" className="text-text-primary">
          <Wordmark />
        </Link>
      </div>
      <div className="relative mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center px-4 pb-24 sm:px-6">
        <p className="kicker mb-5">Error 404</p>
        <h1 className="font-serif text-display text-text-primary">
          No such <em className="text-signal">provision</em>.
        </h1>
        <p className="mt-6 max-w-xl text-lead text-text-secondary">
          The page you asked for is not in this statute book. It may have moved when the app was reorganised, or the
          link may be mistyped.
        </p>
        <div className="mt-10 flex flex-wrap gap-3 text-[14px]">
          <Link href="/" className="rounded-[4px] bg-signal px-4 py-2.5 font-medium text-ink hover:bg-signal-soft">
            Back to the story
          </Link>
          <Link href="/research" className="rounded-[4px] border border-border-light px-4 py-2.5 text-text-primary hover:border-glow">
            Research results
          </Link>
          <Link href="/statutes" className="rounded-[4px] border border-border-light px-4 py-2.5 text-text-primary hover:border-glow">
            Browse statutes
          </Link>
        </div>
      </div>
    </main>
  );
}
