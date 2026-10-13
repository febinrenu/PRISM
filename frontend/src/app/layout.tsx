import type { Metadata, Viewport } from "next";
import { Instrument_Serif } from "next/font/google";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import Providers from "@/components/shell/Providers";

const serif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-serif",
  display: "swap",
});

const SITE = "PRISM: does a machine read the law the way the law reads?";
const DESCRIPTION =
  "PRISM extracts tax rules from Indian statutes with language models, runs them on a population, and checks whether the policy conclusions match expert-coded law, tracing every difference back to a clause.";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
  title: { default: SITE, template: "%s · PRISM" },
  description: DESCRIPTION,
  icons: { icon: "/favicon.svg" },
  openGraph: { title: SITE, description: DESCRIPTION, type: "website", siteName: "PRISM" },
  twitter: { card: "summary_large_image", title: SITE, description: DESCRIPTION },
};

export const viewport: Viewport = {
  themeColor: "#0C0D0E",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${GeistSans.variable} ${GeistMono.variable} ${serif.variable}`}>
      <body className="grain app-shell min-h-dvh bg-bg-base font-sans text-text-primary antialiased">
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
