import type { Metadata } from "next";
import Link from "next/link";
import { ExternalLinkIcon, MapPinIcon, SearchXIcon, TriangleAlertIcon } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { getSavedState } from "@/lib/saved";
import {
  INSTITUTION_TYPES,
  OWNERSHIPS,
  PUBLIC_MARKET_ACCESS,
  STATES,
  hostname,
} from "@/lib/universities";
import { SearchForm } from "@/components/search-form";
import { FilterMenu } from "@/components/filter-menu";
import { SaveButton } from "@/components/save-button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";

export const metadata: Metadata = {
  title: "Hochschulen in Deutschland",
  description:
    "Durchsuche die Hochschulen aus den offiziellen Listen der Bundesländer nach Name, Art, Trägerschaft und Bundesland.",
};

const PAGE_SIZE = 24;

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

// Mehrfachauswahl: "a,b" bzw. ?x=a&x=b → nur gültige Schlüssel, ohne Duplikate
function list(value: string | string[] | undefined, allowed: Record<string, string>) {
  const raw = (Array.isArray(value) ? value : [value ?? ""]).flatMap((v) => v.split(","));
  return [...new Set(raw.map((v) => v.trim()).filter((v) => v in allowed))];
}

function param(value: string | string[] | undefined) {
  return typeof value === "string" ? value.trim() : "";
}

// Seitenzahlen mit Auslassungen, z. B. 1 … 4 5 6 … 18
function pageWindow(page: number, pages: number): (number | "…")[] {
  const set = new Set([1, pages, page - 1, page, page + 1]);
  const nums = [...set].filter((p) => p >= 1 && p <= pages).sort((a, b) => a - b);
  return nums.flatMap((p, i) => (i > 0 && p - nums[i - 1] > 1 ? ["…" as const, p] : [p]));
}

const FILTERS = [
  { name: "typ", label: "Art", all: "Alle Arten", options: INSTITUTION_TYPES },
  { name: "traeger", label: "Trägerschaft", all: "Alle Träger", options: OWNERSHIPS },
  { name: "land", label: "Bundesland", all: "Alle Bundesländer", options: STATES },
] as const;

export default async function UniversitiesPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const q = param(sp.q).slice(0, 100);
  const values = {
    typ: list(sp.typ, INSTITUTION_TYPES),
    traeger: list(sp.traeger, OWNERSHIPS),
    land: list(sp.land, STATES),
  };
  const page = Math.max(1, Number.parseInt(param(sp.seite), 10) || 1);

  const supabase = await createClient();
  let query = supabase
    .from("universities")
    .select(
      "id, name, institution_type, ownership, official_url, listed_by, locations(city, location_type)",
      { count: "exact" }
    )
    .overlaps("market_access", PUBLIC_MARKET_ACCESS)
    .order("name")
    .range((page - 1) * PAGE_SIZE, page * PAGE_SIZE - 1);

  if (q) query = query.ilike("name", `%${q.replace(/[%_\\]/g, "\\$&")}%`);
  if (values.typ.length) query = query.in("institution_type", values.typ);
  if (values.traeger.length) query = query.in("ownership", values.traeger);
  if (values.land.length) query = query.overlaps("listed_by", values.land);

  const { data: universities, count, error } = await query;
  const { signedIn, saved } = await getSavedState((universities ?? []).map((u) => u.id));
  const total = count ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilter = Boolean(q || values.typ.length || values.traeger.length || values.land.length);

  const pageHref = (p: number) => {
    const next = new URLSearchParams();
    if (q) next.set("q", q);
    for (const [k, v] of Object.entries(values)) if (v.length) next.set(k, v.join(","));
    if (p > 1) next.set("seite", String(p));
    const s = next.toString();
    return s ? `/hochschulen?${s}` : "/hochschulen";
  };

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-12 sm:px-6">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
        Hochschulen in Deutschland
      </h1>
      <p className="mt-3 max-w-2xl">
        Alle Einträge stammen aus den offiziellen Hochschullisten der
        Bundesländer.
      </p>

      <SearchForm defaultValue={q} className="mt-8 max-w-3xl">
        <div
          id="filter"
          className="mt-4 grid scroll-mt-28 grid-cols-2 gap-2 *:last:col-span-2 sm:grid-cols-3 sm:gap-3 sm:*:last:col-span-1"
        >
          {FILTERS.map((f) => (
            <FilterMenu
              key={f.name}
              name={f.name}
              label={f.label}
              allLabel={f.all}
              options={f.options}
              value={values[f.name]}
            />
          ))}
        </div>
      </SearchForm>

      {error ? (
        <Alert variant="destructive" className="mt-10">
          <TriangleAlertIcon />
          <AlertTitle>Hochschulen konnten nicht geladen werden</AlertTitle>
          <AlertDescription>Versuch es gleich noch einmal.</AlertDescription>
        </Alert>
      ) : universities.length === 0 ? (
        <Empty className="mt-10 border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <SearchXIcon />
            </EmptyMedia>
            <EmptyTitle>Keine Hochschule gefunden</EmptyTitle>
            <EmptyDescription>
              Probier einen kürzeren Suchbegriff oder entferne Filter.
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button variant="outline" nativeButton={false} render={<Link href="/hochschulen" />}>
              Filter zurücksetzen
            </Button>
          </EmptyContent>
        </Empty>
      ) : (
        <>
          <div className="mt-10 flex items-center justify-between gap-4">
            <p className="text-sm" aria-live="polite">
              {total.toLocaleString("de-DE")} {total === 1 ? "Hochschule" : "Hochschulen"}
              {pages > 1 && ` · Seite ${page} von ${pages}`}
            </p>
            {hasFilter && (
              <Button variant="ghost" size="sm" nativeButton={false} render={<Link href="/hochschulen" />}>
                Filter zurücksetzen
              </Button>
            )}
          </div>

          <ul className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {universities.map((u) => {
              const city =
                u.locations.find((l) => l.location_type === "main")?.city ??
                u.locations[0]?.city;
              const stateCode = u.listed_by.find((s: string) => s in STATES);
              const place = city ?? (stateCode ? STATES[stateCode] : null);
              return (
                <li key={u.id} className="min-w-0">
                  <Card className="relative h-full transition-colors hover:bg-accent/60 hover:ring-accent-foreground/40">
                    <CardHeader>
                      <CardTitle className="leading-snug">
                        <Link href={`/hochschulen/${u.id}`} className="transition-colors group-hover/card:text-accent-foreground after:absolute after:inset-0">
                          {u.name}
                        </Link>
                      </CardTitle>
                      {/* Über dem Link, der die ganze Karte abdeckt */}
                      <CardAction className="relative z-10">
                        <SaveButton
                          compact
                          universityId={u.id}
                          universityName={u.name}
                          saved={saved.has(u.id)}
                          signedIn={signedIn}
                        />
                      </CardAction>
                      <CardDescription className="flex flex-wrap gap-1.5 pt-1">
                        {INSTITUTION_TYPES[u.institution_type] && (
                          <Badge variant="secondary" className="h-auto whitespace-normal">
                            {INSTITUTION_TYPES[u.institution_type]}
                          </Badge>
                        )}
                        {OWNERSHIPS[u.ownership] && (
                          <Badge variant="outline">{OWNERSHIPS[u.ownership]}</Badge>
                        )}
                      </CardDescription>
                    </CardHeader>
                    <CardFooter className="mt-auto flex-wrap gap-x-4 gap-y-1 text-sm">
                      {place && (
                        <span className="inline-flex items-center gap-1">
                          <MapPinIcon className="size-3.5" />
                          {place}
                        </span>
                      )}
                      {u.official_url && (
                        <a
                          href={u.official_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="relative z-10 inline-flex min-w-0 items-center gap-1 break-all hover:text-accent-foreground max-md:-my-2 max-md:py-2"
                        >
                          {hostname(u.official_url)}
                          <ExternalLinkIcon className="size-3.5" />
                        </a>
                      )}
                    </CardFooter>
                  </Card>
                </li>
              );
            })}
          </ul>

          {pages > 1 && (
            <Pagination className="mt-10">
              <PaginationContent>
                {page > 1 && (
                  <PaginationItem>
                    <PaginationPrevious href={pageHref(page - 1)} text="Zurück" aria-label="Vorherige Seite" />
                  </PaginationItem>
                )}
                {pageWindow(page, pages).map((p, i) =>
                  p === "…" ? (
                    <PaginationItem key={`e${i}`}>
                      <PaginationEllipsis />
                    </PaginationItem>
                  ) : (
                    <PaginationItem key={p}>
                      <PaginationLink href={pageHref(p)} isActive={p === page}>
                        {p}
                      </PaginationLink>
                    </PaginationItem>
                  )
                )}
                {page < pages && (
                  <PaginationItem>
                    <PaginationNext href={pageHref(page + 1)} text="Weiter" aria-label="Nächste Seite" />
                  </PaginationItem>
                )}
              </PaginationContent>
            </Pagination>
          )}
        </>
      )}
    </main>
  );
}
