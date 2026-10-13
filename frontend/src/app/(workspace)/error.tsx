"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components/ui/kit";

export default function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);
  const offline = /fetch|network|Failed to fetch/i.test(error.message);
  return (
    <div className="mx-auto max-w-3xl px-4 py-20">
      <ErrorState message={error.message} onRetry={reset} offline={offline} />
    </div>
  );
}
