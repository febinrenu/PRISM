import TopBar from "@/components/shell/TopBar";
import SiteFooter from "@/components/shell/SiteFooter";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
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
