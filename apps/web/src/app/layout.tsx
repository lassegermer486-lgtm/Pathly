import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { Analytics } from "@/components/analytics";
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
    "Pathly soll dich von der Studienwahl bis zum Berufseinstieg begleiten. Wir starten mit den Hochschulen in Deutschland, aus den offiziellen Listen der Bundesländer.",
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
      className={`${geistSans.variable} ${geistMono.variable} h-full overflow-x-clip antialiased`}
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
