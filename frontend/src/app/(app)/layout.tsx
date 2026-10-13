import TopBar from "@/components/shell/TopBar";
import SiteFooter from "@/components/shell/SiteFooter";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <TopBar />
      <main id="main" className="relative">
        {children}
      </main>
      <SiteFooter />
    </>
  );
}
