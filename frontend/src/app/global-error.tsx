"use client";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ background: "#0C0D0E", color: "#F1EDE4", fontFamily: "system-ui, sans-serif", padding: 40 }}>
        <h1 style={{ fontWeight: 400 }}>PRISM hit an unexpected error.</h1>
        <button type="button" onClick={reset} style={{ marginTop: 16, padding: "8px 14px" }}>
          Try again
        </button>
      </body>
    </html>
  );
}
