import Image from "next/image";
import {
  BadgeCheckIcon,
  BuildingIcon,
  CompassIcon,
  GraduationCapIcon,
  ScaleIcon,
} from "lucide-react";
import { PROVIDER } from "@/lib/legal";
import { list } from "@/lib/search-params";
import { createClient } from "@/lib/supabase/server";
import { PUBLIC_MARKET_ACCESS, STATES, UNIVERSITY_FILTERS } from "@/lib/universities";
import { FilterMenu } from "@/components/filter-menu";
import { SearchForm } from "@/components/search-form";
import { Glow } from "@/components/glow";
import { CtaButton } from "@/components/cta-button";
import { CharReveal } from "@/components/char-reveal";
import { GermanyMap } from "@/components/germany-map";
import { HeroFlag } from "@/components/hero-flag";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";

const ROADMAP = [
  { title: "Hochschulregister", text: "Hochschulen in Deutschland mit Standort, Trägerschaft und Quelle.", status: "Live" },
  { title: "Studiengänge & Zulassung", text: "Welcher Studiengang passt zu deinem Abschluss? Voraussetzungen, Tests und Studienmodelle auf einen Blick, statt Hochschule für Hochschule zu suchen.", status: "Geplant" },
  { title: "Kosten & Leben vor Ort", text: "Gebühren, Miete und Lebenshaltung am Studienort, damit du abschätzen kannst, wie viel du nebenbei verdienen müsstest.", status: "Geplant" },
  { title: "Auslandssemester", text: "Partnerhochschulen und Allianzen als klare Übersicht, damit du siehst, wohin du von deiner Hochschule aus gehen kannst.", status: "Geplant" },
  { title: "Rankings & Bewertungen", text: "Rankings mit offener Methodik und Erfahrungen von Menschen, die nachweislich dort studieren.", status: "Geplant" },
  { title: "Karriere & Bewerbung", text: "Welche Wege führen in welchen Beruf, und brauchst du dafür einen Master? Dazu Lebenslauf-Feedback und Vorbereitung auf Interviews und Case Studies.", status: "Geplant" },
];

const PRINCIPLES = [
  { icon: BadgeCheckIcon, title: "Offizielle Quellen", text: "Unsere Daten stammen aus den Hochschullisten der Landesministerien. Zu jedem Eintrag zeigen wir, woher er kommt." },
  { icon: ScaleIcon, title: "Transparente Methodik", text: "Wenn wir etwas bewerten oder einschätzen, legen wir Faktoren und Gewichtung offen." },
  { icon: CompassIcon, title: "Keine Garantien", text: "Wir zeigen Wege und Einschätzungen, keine Versprechen. Jedes Profil ist anders, und auch ungewöhnliche Bildungswege können ans Ziel führen." },
];

const PARTNERS = [
  { icon: GraduationCapIcon, title: "Hochschulen", text: "Jede Hochschule aus den offiziellen Listen steht bei uns gleichberechtigt, auch abseits der bekannten Rankings. So können auch kleinere Hochschulen gefunden werden." },
  { icon: BuildingIcon, title: "Unternehmen", text: "Studierende sollen früh sehen, welche Wege in welche Branchen führen. Dazu möchten wir mit Unternehmen sprechen, die zeigen wollen, wen sie suchen." },
];

export default async function Home({ searchParams }: PageProps<"/">) {
  const sp = await searchParams;
  const supabase = await createClient();
  // Eine Abfrage liefert Gesamtzahl und Anzahl je Bundesland (für die Karte)
  const { data: listed } = await supabase
    .from("universities")
    .select("listed_by")
    .overlaps("market_access", PUBLIC_MARKET_ACCESS)
    .limit(5000);
  const count = listed?.length ?? null;
  const counts: Record<string, number> = {};
  for (const row of listed ?? []) {
    for (const code of row.listed_by as string[]) {
      if (code in STATES) counts[code] = (counts[code] ?? 0) + 1;
    }
  }

  return (
    <main className="flex-1">
      {/* Einstieg mit Tiefe: Foto, darüber das große Wort, darüber der freigestellte Berg */}
      <section className="px-3 pt-3 sm:px-4">
        {/* --hero-offset: Auf schmalen Bildschirmen rückt der Berg nach unten, damit die Flagge
            nicht das Wort verdeckt (genauer Wert aus HeroFlag). Der Hintergrund hat die Farbe des Himmels. */}
        <div className="relative isolate mx-auto flex h-[calc(100svh-6.5rem)] max-h-[56rem] min-h-[36rem] max-w-[110rem] flex-col justify-end overflow-hidden rounded-3xl bg-[#dbe6f0] [--hero-offset:0px] max-lg:[--hero-offset:22vw]">
          <div className="absolute inset-x-0 top-(--hero-offset) bottom-0 -z-30 max-lg:[mask-image:linear-gradient(to_bottom,transparent,black_5rem)]">
            <Image
              src="/images/hero/hero.jpg"
              alt=""
              fill
              priority
              sizes="100vw"
              className="object-cover object-[60%_top]"
            />
          </div>
          <div aria-hidden data-hero-word className="absolute inset-x-0 top-[3%] -z-20 text-center">
            <CharReveal
              text="Klarheit"
              className="block text-[23vw] leading-none font-medium tracking-tight text-brand-forest min-[110rem]:text-[25rem]"
            />
          </div>
          <div className="absolute inset-x-0 top-(--hero-offset) bottom-0 -z-10">
            <Image
              src="/images/hero/hero-vorne.webp"
              alt=""
              fill
              priority
              sizes="100vw"
              className="object-cover object-[60%_top]"
            />
          </div>
          <div aria-hidden className="absolute inset-x-0 bottom-0 -z-10 h-2/3 bg-gradient-to-t from-black/70 via-black/35 to-transparent" />
          <HeroFlag />

          <div className="flex flex-wrap items-end justify-between gap-6 p-5 text-white sm:p-8">
            <div className="max-w-2xl animate-fade-up" style={{ animationDelay: "500ms" }}>
              <h1 className="text-4xl leading-[1.05] tracking-tight text-balance sm:text-6xl">
                <span className="sr-only">Klarheit </span>für deinen nächsten Schritt
              </h1>
              <p className="mt-4 max-w-xl text-pretty sm:text-lg">
                Was willst du später arbeiten, und welcher Weg führt dorthin? Pathly soll
                dich von der Studienwahl bis zum Berufseinstieg begleiten.
              </p>
              <CtaButton href="/hochschulen" className="mt-6">
                Hochschulen ansehen
              </CtaButton>
            </div>
            <p
              className="animate-fade-up rounded-2xl bg-background/90 p-4 text-sm text-foreground backdrop-blur max-sm:hidden"
              style={{ animationDelay: "700ms" }}
            >
              <span className="block text-3xl font-medium tracking-tight text-primary">
                {count?.toLocaleString("de-DE") ?? "Über 400"}
              </span>
              Hochschulen aus den offiziellen
              <br />
              Listen aller 16 Bundesländer
            </p>
          </div>
        </div>
      </section>

      <section id="hochschulen" className="scroll-mt-24">
        <div className="mx-auto grid w-full max-w-6xl items-center gap-10 px-4 pt-14 pb-16 sm:px-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div>
            <h2 className="text-4xl tracking-tight text-primary">Finde deine Hochschule</h2>
            <p className="mt-3 max-w-xl text-muted-foreground">
              Wir starten mit den {count?.toLocaleString("de-DE") ?? "über 400"} Hochschulen aus den
              offiziellen Listen aller 16 Bundesländer.
            </p>
            <SearchForm className="mt-8 max-w-xl">
              <div className="mt-4 grid grid-cols-2 gap-2 *:last:col-span-2 sm:grid-cols-3 sm:gap-3 sm:*:last:col-span-1">
                {UNIVERSITY_FILTERS.map((f) => (
                  <FilterMenu
                    key={f.name}
                    name={f.name}
                    label={f.label}
                    allLabel={f.all}
                    options={f.options}
                    value={list(sp[f.name], f.options)}
                  />
                ))}
              </div>
            </SearchForm>
          </div>
          {/* Karte als Einstieg: Bundesland anklicken öffnet die Suche mit diesem Filter */}
          <GermanyMap counts={counts} className="mx-auto w-full max-w-sm sm:max-w-md lg:max-w-none" />
        </div>
      </section>

      <section id="vorhaben" className="scroll-mt-24">
        <div className="mx-auto max-w-6xl px-4 pt-8 pb-24 sm:px-6 sm:pt-12">
          <h2 className="text-4xl tracking-tight text-primary">Was kommt</h2>
          <p className="mt-3 max-w-2xl text-muted-foreground">
            Oft geht es zuerst darum, was du studieren willst. Wir fragen auch,
            was du danach arbeiten möchtest. Darum wächst Pathly in drei Etappen:
            Studienwahl, Studium und Berufseinstieg. Du kannst dich selbst
            durchklicken und sollst später auch eine KI-Beratung fragen können,
            die ihre Quellen nennt.
          </p>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {ROADMAP.map((item) => (
              <Card key={item.title} className="rounded-2xl">
                <CardHeader>
                  <CardTitle>{item.title}</CardTitle>
                  <CardAction>
                    <Badge
                      variant={item.status === "Geplant" ? "outline" : "default"}
                      className={item.status === "Live" ? "bg-brand-mint text-brand-primary" : item.status === "In Arbeit" ? "bg-brand-aqua text-brand-forest" : undefined}
                    >
                      {item.status}
                    </Badge>
                  </CardAction>
                </CardHeader>
                <CardContent>
                  <p className="text-muted-foreground">{item.text}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section id="prinzipien" className="scroll-mt-24">
        <div className="mx-auto max-w-6xl px-4 pt-12 pb-8 sm:px-6 sm:pt-16">
          <h2 className="text-4xl tracking-tight text-primary">Worauf du dich verlassen kannst</h2>
          <ItemGroup className="mt-10 grid gap-4 sm:grid-cols-3">
            {PRINCIPLES.map(({ icon: Icon, title, text }) => (
              <Item key={title} variant="outline" className="items-start rounded-2xl p-5">
                <ItemMedia variant="icon" className="rounded-full bg-accent p-2.5">
                  <Icon className="size-5 text-accent-foreground" />
                </ItemMedia>
                <ItemContent>
                  <ItemTitle className="text-base">{title}</ItemTitle>
                  <ItemDescription className="line-clamp-none">{text}</ItemDescription>
                </ItemContent>
              </Item>
            ))}
          </ItemGroup>
        </div>
      </section>

      <section id="partner" className="scroll-mt-24">
        <div className="mx-auto max-w-6xl px-4 pt-12 pb-8 sm:px-6 sm:pt-16">
          <h2 className="text-4xl tracking-tight text-primary">Für Hochschulen und Unternehmen</h2>
          <p className="mt-3 max-w-2xl text-muted-foreground">
            Pathly soll mehr werden als ein Verzeichnis: Wir verbinden Hochschulen,
            Studiengänge und Berufswege. Dafür suchen wir das Gespräch.
          </p>
          <ItemGroup className="mt-10 grid gap-4 sm:grid-cols-2">
            {PARTNERS.map(({ icon: Icon, title, text }) => (
              <Item key={title} variant="outline" className="items-start rounded-2xl p-5">
                <ItemMedia variant="icon" className="rounded-full bg-accent p-2.5">
                  <Icon className="size-5 text-accent-foreground" />
                </ItemMedia>
                <ItemContent>
                  <ItemTitle className="text-base">{title}</ItemTitle>
                  <ItemDescription className="line-clamp-none">{text}</ItemDescription>
                </ItemContent>
              </Item>
            ))}
          </ItemGroup>
          <Button
            variant="outline"
            className="mt-6"
            nativeButton={false}
            render={<a href={`mailto:${PROVIDER.email}`} />}
          >
            Kontakt aufnehmen
          </Button>
        </div>
      </section>

      {/* Abschluss: gleicher Schimmer wie oben, gespiegelt – läuft hinter die Fußzeile aus */}
      <section className="relative px-4 pt-16 pb-20 text-center sm:px-6 sm:pt-20 sm:pb-24">
        <Glow edge="bottom" />
        <h2 className="mx-auto max-w-2xl text-4xl tracking-tight text-balance text-primary sm:text-5xl">
          Bereit, deinen Weg zu <span className="text-brand-green">finden</span>?
        </h2>
        <p className="mx-auto mt-4 max-w-md text-muted-foreground">
          Starte mit den Hochschulen: Such nach Name, Art, Trägerschaft und Bundesland.
        </p>
        <div className="mt-8 flex justify-center">
          <CtaButton href="/hochschulen">Hochschulen entdecken</CtaButton>
        </div>
      </section>
    </main>
  );
}
