import TopBar from "@/components/shell/TopBar";

/** Workspace routes fill the viewport under the top bar; no footer. */
export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <TopBar />
      <main id="main" className="relative">
        {children}
      </main>
    </>
  );
}
