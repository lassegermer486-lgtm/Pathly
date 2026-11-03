"use client";

import { useState } from "react";
import Link from "next/link";
import germanyData from "@svg-maps/germany";
import { ArrowRightIcon, MapPinIcon } from "lucide-react";
import { STATES } from "@/lib/universities";
import { cn } from "@/lib/utils";

// Interaktive Deutschlandkarte: Bundesland hovern/fokussieren zeigt Name und
// Anzahl der Hochschulen, Klick öffnet die Suche mit diesem Bundesland.
// Kartendaten: @svg-maps/germany (CC BY 4.0) – Quellenhinweis unter der Karte.
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

      {/* Info zum aktiven Bundesland; ohne Auswahl ein Hinweis */}
      <div
        aria-live="polite"
        className="pointer-events-none absolute top-2 left-0 rounded-2xl bg-white/80 px-4 py-3 shadow-sm ring-1 ring-primary/8 backdrop-blur-sm"
      >
        {activeCode ? (
          <>
            <p className="flex items-center gap-1.5 font-medium text-primary">
              <MapPinIcon className="size-4" />
              {STATES[activeCode]}
            </p>
            <p className="mt-0.5 flex items-center gap-1 text-sm text-muted-foreground">
              {counts[activeCode] ?? 0} Hochschulen ansehen
              <ArrowRightIcon className="size-3.5" />
            </p>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">Bundesland wählen</p>
        )}
      </div>

      <p className="absolute right-0 bottom-0 text-[10px] text-muted-foreground/70">
        Karte:{" "}
        <a
          href="https://github.com/VictorCazanave/svg-maps"
          target="_blank"
          rel="noopener noreferrer"
          className="pointer-events-auto underline-offset-2 hover:underline"
        >
          svg-maps
        </a>
        , CC BY 4.0
      </p>
    </div>
  );
}
