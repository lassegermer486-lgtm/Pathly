import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalLinkIcon, LandmarkIcon, MapPinIcon } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { campusDataUrl } from "@/lib/campus";
import { universityLogo } from "@/lib/logos";
import { getSavedState } from "@/lib/saved";
import {
  INSTITUTION_TYPES,
  OWNERSHIPS,
  PUBLIC_MARKET_ACCESS,
  STATES,
  hostname,
} from "@/lib/universities";
import { CampusMap } from "@/components/campus-map";
import { SaveButton } from "@/components/save-button";
import { Badge } from "@/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";

type University = {
  id: number;
  registry_id: string;
  name: string;
  name_variants: string[];
  institution_type: string;
  ownership: string;
  official_url: string | null;
  listed_by: string[];
  locations: {
    id: number;
    name: string | null;
    street: string | null;
    postal_code: string | null;
    city: string | null;
    state: string | null;
    location_type: string;
  }[];
  sources: {
    id: number;
    state: string | null;
    authority: string | null;
    url: string | null;
    retrieved_at: string | null;
  }[];
};

async function getUniversity(rawId: string) {
  if (!/^\d+$/.test(rawId)) return null;
  const supabase = await createClient();
  const { data } = await supabase
    .from("universities")
    .select(
      "id, registry_id, name, name_variants, institution_type, ownership, official_url, listed_by, " +
        "locations(id, name, street, postal_code, city, state, location_type), " +
        "sources(id, state, authority, url, retrieved_at)"
    )
    .eq("id", Number(rawId))
    .overlaps("market_access", PUBLIC_MARKET_ACCESS)
    .maybeSingle();
  return data as University | null;
}

export async function generateMetadata({
  params,
}: PageProps<"/hochschulen/[id]">): Promise<Metadata> {
  const u = await getUniversity((await params).id);
  if (!u) return { title: "Hochschule nicht gefunden" };
  return {
    title: u.name,
    description: `${u.name}: Art, Trägerschaft, Standorte und offizielle Quelle auf Pathly.`,
  };
}

export default async function UniversityPage({
  params,
}: PageProps<"/hochschulen/[id]">) {
  const u = await getUniversity((await params).id);
  if (!u) notFound();

  const { signedIn, saved } = await getSavedState([u.id]);
  const campusUrl = campusDataUrl(u.registry_id);
  const logo = universityLogo(u.registry_id);

  const facts = [
    ["Art", INSTITUTION_TYPES[u.institution_type]],
    ["Trägerschaft", OWNERSHIPS[u.ownership]],
    ["Bundesland", u.listed_by.filter((s) => s in STATES).map((s) => STATES[s]).join(", ")],
  ].filter(([, v]) => v);

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-12 sm:px-6">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink render={<Link href="/hochschulen" />}>Hochschulen</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage className="line-clamp-1">{u.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {logo && (
        <Image
          src={logo.src}
          width={logo.width}
          height={logo.height}
          alt={`Logo: ${u.name}`}
          className="mt-6 h-12 w-auto max-w-full object-contain sm:h-14"
        />
      )}

      <h1 className="mt-6 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
        {u.name}
      </h1>
      {u.name_variants.length > 0 && (
        <p className="mt-2">Auch bekannt als: {u.name_variants.join(", ")}</p>
      )}

      <div className="mt-6 flex flex-wrap items-start gap-3">
        {u.official_url && (
          <Button
            size="lg"
            className="h-10 max-w-full shrink px-4"
            nativeButton={false}
            render={<a href={u.official_url} target="_blank" rel="noopener noreferrer" />}
          >
            <span className="truncate">{hostname(u.official_url)}</span>
            <ExternalLinkIcon data-icon="inline-end" />
          </Button>
        )}
        <SaveButton
          universityId={u.id}
          universityName={u.name}
          saved={saved.has(u.id)}
          signedIn={signedIn}
        />
      </div>

      {facts.length > 0 && (
        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          {facts.map(([label, value]) => (
            <Card key={label} size="sm">
              <CardHeader>
                <CardDescription>{label}</CardDescription>
                <CardTitle>{value}</CardTitle>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}

      {u.locations.length > 0 && (
        <section className="mt-12">
          <h2 className="text-xl font-semibold">Standorte</h2>
          <ItemGroup className="mt-4 gap-3">
            {u.locations.map((l) => (
              <Item key={l.id} variant="outline">
                <ItemMedia variant="icon">
                  <MapPinIcon className="text-accent-foreground" />
                </ItemMedia>
                <ItemContent>
                  <ItemTitle>
                    {l.name ?? l.city ?? "Standort"}
                    {l.location_type === "main" && <Badge variant="secondary">Hauptsitz</Badge>}
                  </ItemTitle>
                  <ItemDescription className="text-foreground">
                    {[l.street, [l.postal_code, l.city].filter(Boolean).join(" ")]
                      .filter(Boolean)
                      .join(", ")}
                  </ItemDescription>
                </ItemContent>
              </Item>
            ))}
          </ItemGroup>
        </section>
      )}

      {campusUrl && <CampusMap dataUrl={campusUrl} />}

      {u.sources.length > 0 && (
        <section className="mt-12">
          <h2 className="text-xl font-semibold">Quellen</h2>
          <p className="mt-1 text-sm">Woher die Angaben auf dieser Seite stammen.</p>
          <ItemGroup className="mt-4 gap-3">
            {u.sources.map((s) => (
              <Item
                key={s.id}
                variant="outline"
                render={s.url ? <a href={s.url} target="_blank" rel="noopener noreferrer" /> : undefined}
              >
                <ItemMedia variant="icon">
                  <LandmarkIcon />
                </ItemMedia>
                <ItemContent>
                  <ItemTitle>{s.authority ?? (s.url ? hostname(s.url) : "Landesquelle")}</ItemTitle>
                  {s.retrieved_at && (
                    <ItemDescription className="text-foreground">
                      Abgerufen am {new Date(s.retrieved_at).toLocaleDateString("de-DE")}
                    </ItemDescription>
                  )}
                </ItemContent>
                {s.url && <ExternalLinkIcon className="size-4" />}
              </Item>
            ))}
          </ItemGroup>
        </section>
      )}
    </main>
  );
}
