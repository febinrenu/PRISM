export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main id="main" className="relative min-h-dvh">
      {children}
    </main>
  );
}
