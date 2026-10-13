import Link from "next/link";

export default function StoryPage() {
  return (
    <main id="main" className="relative flex min-h-dvh flex-col items-start justify-center px-6">
      <h1 className="font-serif text-display">A law is a program nobody runs.</h1>
      <Link href="/start" className="mt-8 text-signal underline">Analyse a PDF</Link>
    </main>
  );
}
