import type { Metadata } from "next";
import { Manrope, Playfair_Display, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

const manrope = Manrope({ subsets: ["latin"], variable: "--font-manrope" });
const playfair = Playfair_Display({ subsets: ["latin"], variable: "--font-playfair" });
const jetbrainsMono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "PRISM — Legal Intelligence Platform",
  description:
    "PRISM reads legal documents, extracts structured intelligence, and maps societal impact — with full explainability.",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${manrope.variable} ${playfair.variable} ${jetbrainsMono.variable}`}>
      <body className="antialiased min-h-screen app-shell font-sans bg-bg-base text-text-primary">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
