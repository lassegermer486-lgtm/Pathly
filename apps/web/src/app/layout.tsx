import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://pathly.info"),
  title: {
    default: "Pathly – Orientierung für Studium und Karriere",
    template: "%s · Pathly",
  },
  description:
    "Alle staatlich anerkannten Hochschulen in Deutschland an einem Ort – aus offiziellen Quellen der Bundesländer, transparent und ohne Versprechen.",
  openGraph: {
    type: "website",
    locale: "de_DE",
    siteName: "Pathly",
    url: "https://pathly.info",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="de"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <SiteHeader />
        {children}
        <SiteFooter />
        <Analytics />
      </body>
    </html>
  );
}
