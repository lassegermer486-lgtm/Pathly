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
      {/* Einstieg: Ab lg steht das ganze Foto in voller Höhe rechts und läuft links in den Himmel aus,
          daneben steht der Text. Darunter steht der Text oben und das Foto beginnt erst darunter.
          Der Rahmen hat die Farbe des Himmels oben im Foto. */}
      <section className="px-3 pt-3 sm:px-4">
        <div className="relative isolate mx-auto flex min-h-[44rem] max-w-[110rem] flex-col max-sm:min-h-[48rem] max-[360px]:min-h-[52rem] overflow-hidden rounded-3xl bg-[#cddceb] lg:h-[calc(100svh-6.5rem)] lg:max-h-[56rem] lg:min-h-[36rem] lg:justify-center">
          <div
            data-hero-photo
            className="absolute inset-y-0 left-0 -z-30 w-full max-lg:top-[19rem] max-sm:top-[24rem] max-[360px]:top-[29rem] max-lg:[mask-image:linear-gradient(to_bottom,transparent,black_5rem)] lg:right-0 lg:left-auto lg:aspect-[2400/1548] lg:w-auto lg:translate-x-[15%] lg:[mask-image:linear-gradient(to_right,transparent,black_32%)]"
          >
            <Image
              src="/images/hero/hero.jpg"
              alt=""
              fill
              priority
              sizes="(min-width: 1024px) 80vw, 100vw"
              className="object-cover object-[72%_top] lg:object-[0%_top]"
            />
          </div>
          <HeroFlag />

          <div className="max-w-2xl p-5 sm:p-8 lg:w-1/2 lg:pl-12">
            <CharReveal
              as="h1"
              text="Klarheit für deinen nächsten Schritt"
              className="block text-4xl leading-[1.05] tracking-tight text-brand-forest sm:text-6xl xl:text-7xl"
            />
            <p
              className="mt-5 max-w-xl animate-fade-up text-pretty text-brand-forest sm:text-lg"
              style={{ animationDelay: "500ms" }}
            >
              Was willst du später arbeiten, und welcher Weg führt dorthin? Pathly soll
              dich von der Studienwahl bis zum Berufseinstieg begleiten.
            </p>
            <div className="mt-6 animate-fade-up" style={{ animationDelay: "650ms" }}>
              <CtaButton href="/hochschulen">Hochschulen ansehen</CtaButton>
            </div>
          </div>

          <p
            className="absolute right-5 bottom-5 animate-fade-up rounded-2xl bg-background/90 p-4 text-sm text-foreground backdrop-blur max-sm:hidden sm:right-8 sm:bottom-8"
            style={{ animationDelay: "800ms" }}
          >
            <span className="block text-3xl font-medium tracking-tight text-primary">
              {count?.toLocaleString("de-DE") ?? "Über 400"}
            </span>
            Hochschulen aus den offiziellen
            <br />
            Listen aller 16 Bundesländer
          </p>
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
