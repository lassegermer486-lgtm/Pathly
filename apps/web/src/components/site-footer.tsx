import Link from "next/link";
import { Logo } from "@/components/logo";
import { Button } from "@/components/ui/button";

const LINKS = [
  { href: "/hochschulen", label: "Hochschulen" },
  { href: "/impressum", label: "Impressum" },
  { href: "/datenschutz", label: "Datenschutz" },
];

export function SiteFooter() {
  return (
    <footer className="mt-auto">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="space-y-2">
          <Logo />
          <p className="text-sm">Orientierung für Studium und Karriere.</p>
        </div>
        <nav className="-ml-2.5 flex flex-wrap gap-1 sm:ml-0">
          {LINKS.map((l) => (
            <Button key={l.href} variant="ghost" nativeButton={false} render={<Link href={l.href} />}>
              {l.label}
            </Button>
          ))}
        </nav>
      </div>
    </footer>
  );
}
