"use client";

import { useState } from "react";
import Link from "next/link";
import germanyData from "@svg-maps/germany";
import { ArrowRightIcon, MapPinIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { STATES } from "@/lib/universities";
import { cn } from "@/lib/utils";

// Interaktive Deutschlandkarte: Bundesland hovern/fokussieren zeigt Name und
// Anzahl der Hochschulen, Klick öffnet die Suche mit diesem Bundesland.
// Kartendaten: @svg-maps/germany (CC BY 4.0) – Quellenhinweis im Impressum (Quellen und Lizenzen).
type SvgMap = { viewBox: string; locations: { id: string; name: string; path: string }[] };
const germany = germanyData as unknown as SvgMap;
// Stadtstaaten innerhalb anderer Länder zuletzt zeichnen, damit sie oben liegen und klickbar sind
const ENCLAVES = new Set(["be", "hb"]);
const LOCATIONS = [...germany.locations].sort(
  (a, b) => Number(ENCLAVES.has(a.id)) - Number(ENCLAVES.has(b.id))
);
export function GermanyMap({ counts, className }: { counts: Record<string, number>; className?: string }) {
  const [active, setActive] = useState<string | null>(null);
  const activeCode = active ? `DE-${active.toUpperCase()}` : null;

  return (
    <div className={cn("relative", className)}>
      <svg
        viewBox={germany.viewBox}
        className="h-auto w-full drop-shadow-[0_1px_1px_rgb(4_75_57/0.08)]"
        role="group"
        aria-label="Deutschlandkarte: Bundesland wählen"
      >
        {LOCATIONS.map((loc) => {
          const code = `DE-${loc.id.toUpperCase()}`;
          const name = STATES[code] ?? loc.name;
          const count = counts[code] ?? 0;
          const isActive = active === loc.id;
          return (
            <Link
              key={loc.id}
              href={`/hochschulen?land=${code}`}
              aria-label={`${name}: ${count} Hochschulen anzeigen`}
              onMouseEnter={() => setActive(loc.id)}
              onMouseLeave={() => setActive((a) => (a === loc.id ? null : a))}
              onFocus={() => setActive(loc.id)}
              onBlur={() => setActive((a) => (a === loc.id ? null : a))}
              className="outline-none"
            >
              <path
                d={loc.path}
                className={cn(
                  "cursor-pointer stroke-white stroke-[1.5] transition-colors duration-200",
                  isActive ? "fill-brand-green" : "fill-brand-mint"
                )}
              />
            </Link>
          );
        })}
      </svg>

      {/* Info nur beim Hovern/Fokussieren eines Bundeslands */}
      <div aria-live="polite" className="pointer-events-none absolute top-2 left-0">
        {activeCode && (
          <div className="rounded-2xl bg-white/80 px-4 py-3 shadow-sm ring-1 ring-primary/8 backdrop-blur-sm">
            <p className="flex items-center gap-1.5 font-medium text-primary">
              <MapPinIcon className="size-4" />
              {STATES[activeCode]}
            </p>
            <p className="mt-0.5 flex items-center gap-1 text-sm text-muted-foreground">
              {counts[activeCode] ?? 0} Hochschulen ansehen
              <ArrowRightIcon className="size-3.5" />
            </p>
          </div>
        )}
      </div>

      {/* Touch-Geräte haben kein Hovern und kleine Länder sind schwer zu treffen */}
      <nav aria-label="Hochschulen nach Bundesland" className="mt-6 grid grid-cols-1 gap-1 min-[420px]:grid-cols-2 lg:hidden">
        {Object.entries(STATES).map(([code, name]) => (
          <Button
            key={code}
            variant="ghost"
            className="justify-between font-normal"
            nativeButton={false}
            render={<Link href={`/hochschulen?land=${code}`} />}
          >
            {name}
            <span className="text-muted-foreground tabular-nums">{counts[code] ?? 0}</span>
          </Button>
        ))}
      </nav>
    </div>
  );
}
