import type { Metadata } from "next";
import Link from "next/link";
import { ExternalLinkIcon, MapPinIcon, SearchXIcon, TriangleAlertIcon } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import {
  INSTITUTION_TYPES,
  OWNERSHIPS,
  PUBLIC_MARKET_ACCESS,
  STATES,
  hostname,
} from "@/lib/universities";
import { SearchForm } from "@/components/search-form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
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
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
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
    "Durchsuche alle staatlich anerkannten Hochschulen in Deutschland nach Name, Art, Trägerschaft und Bundesland.",
};

const PAGE_SIZE = 24;

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

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
  const values = { typ: param(sp.typ), traeger: param(sp.traeger), land: param(sp.land) };
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
  if (values.typ in INSTITUTION_TYPES) query = query.eq("institution_type", values.typ);
  if (values.traeger in OWNERSHIPS) query = query.eq("ownership", values.traeger);
  if (values.land in STATES) query = query.contains("listed_by", [values.land]);

  const { data: universities, count, error } = await query;
  const total = count ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilter = Boolean(q || values.typ || values.traeger || values.land);

  const pageHref = (p: number) => {
    const next = new URLSearchParams();
    if (q) next.set("q", q);
    for (const [k, v] of Object.entries(values)) if (v) next.set(k, v);
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
        <FieldGroup className="mt-4 grid gap-3 sm:grid-cols-3">
          {FILTERS.map((f) => (
            <Field key={f.name} className="gap-1.5">
              <FieldLabel htmlFor={`filter-${f.name}`}>{f.label}</FieldLabel>
              <NativeSelect id={`filter-${f.name}`} name={f.name} defaultValue={values[f.name]} className="w-full">
                <NativeSelectOption value="">{f.all}</NativeSelectOption>
                {Object.entries(f.options).map(([value, label]) => (
                  <NativeSelectOption key={value} value={value}>
                    {label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </Field>
          ))}
        </FieldGroup>
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
                <li key={u.id}>
                  <Card className="relative h-full transition-colors hover:bg-accent/60 hover:ring-accent-foreground/40">
                    <CardHeader>
                      <CardTitle className="leading-snug">
                        <Link href={`/hochschulen/${u.id}`} className="transition-colors group-hover/card:text-accent-foreground after:absolute after:inset-0">
                          {u.name}
                        </Link>
                      </CardTitle>
                      <CardDescription className="flex flex-wrap gap-1.5 pt-1">
                        {INSTITUTION_TYPES[u.institution_type] && (
                          <Badge variant="secondary">{INSTITUTION_TYPES[u.institution_type]}</Badge>
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
                          className="relative z-10 inline-flex items-center gap-1 hover:text-accent-foreground"
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
