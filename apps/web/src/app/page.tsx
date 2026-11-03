import Link from "next/link";
import { BadgeCheckIcon, CompassIcon, ScaleIcon } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { PUBLIC_MARKET_ACCESS, STATES } from "@/lib/universities";
import { SearchForm } from "@/components/search-form";
import { HeroScene } from "@/components/hero-scene";
import { Glow } from "@/components/glow";
import { CtaButton } from "@/components/cta-button";
import { CharReveal } from "@/components/char-reveal";
import { Badge } from "@/components/ui/badge";
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
  { title: "Hochschulregister", text: "Alle Hochschulen in Deutschland mit Standort, Trägerschaft und Quelle.", status: "Live" },
  { title: "Studiengänge", text: "Welche Hochschule bietet was an – vergleichbar statt verstreut.", status: "In Arbeit" },
  { title: "Zulassung Bachelor → Master", text: "Voraussetzungen nebeneinander, damit der Übergang planbar wird.", status: "Geplant" },
  { title: "Kosten & Lebenshaltung", text: "Studiengebühren, Semesterbeitrag und Lebenshaltung am Studienort.", status: "Geplant" },
  { title: "Nachvollziehbare Rankings", text: "Eigene Rankings mit offener Methodik statt Blackbox.", status: "Geplant" },
  { title: "Verifizierte Bewertungen", text: "Erfahrungen nur von nachweislich Studierenden der Hochschule.", status: "Geplant" },
];

const PRINCIPLES = [
  { icon: BadgeCheckIcon, title: "Offizielle Quellen", text: "Unsere Daten stammen aus den Hochschullisten der Landesministerien. Zu jedem Eintrag zeigen wir, woher er kommt." },
  { icon: ScaleIcon, title: "Transparente Methodik", text: "Jede Bewertung, jeder Faktor und jede Gewichtung wird offen dokumentiert." },
  { icon: CompassIcon, title: "Keine Garantien", text: "Wir zeigen Wege und Wahrscheinlichkeiten – keine Versprechen. Auch ungewöhnliche Bildungswege können ans Ziel führen." },
];

export default async function Home() {
  const supabase = await createClient();
  const { count } = await supabase
    .from("universities")
    .select("id", { count: "exact", head: true })
    .overlaps("market_access", PUBLIC_MARKET_ACCESS);

  return (
    <main className="flex-1">
      <HeroScene>
        <div className="mx-auto w-full max-w-6xl px-4 sm:px-6">
          <CharReveal
            as="h1"
            text="Klarheit für deine Studienwahl"
            accent="Studienwahl"
            className="block max-w-4xl text-5xl leading-[1.05] tracking-tight text-primary sm:text-7xl"
          />
          <p
            className="mt-6 max-w-xl animate-fade-up text-lg text-pretty text-muted-foreground"
            style={{ animationDelay: "500ms" }}
          >
            Alle Hochschulen in Deutschland an einem Ort – geprüft, mit Quelle
            und verständlich aufbereitet.
          </p>
        </div>

        <div className="mx-auto mt-12 grid w-full max-w-6xl gap-10 px-4 sm:px-6 lg:grid-cols-[1fr_1.3fr]">
          <div className="flex animate-fade-up flex-col gap-6" style={{ animationDelay: "700ms" }}>
            <p className="text-sm">
              <span className="font-medium">{count?.toLocaleString("de-DE") ?? "Über 400"} Hochschulen</span>{" "}
              aus den offiziellen Listen aller 16 Bundesländer
            </p>
            <SearchForm className="max-w-md" />
            <div>
              <CtaButton href="/hochschulen">Alle Hochschulen ansehen</CtaButton>
            </div>
          </div>
          {/* Bundesländer als Einstieg: jede Kachel öffnet die Suche mit diesem Filter */}
          <nav aria-label="Hochschulen nach Bundesland">
            <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                ...Object.entries(STATES)
                  .slice(0, 7)
                  .map(([code, name]) => ({ href: `/hochschulen?land=${code}`, label: name })),
                { href: "/hochschulen#filter", label: "+ 9 weitere" },
              ].map((tile, i) => (
                <li key={tile.href} className="animate-fade-up" style={{ animationDelay: `${900 + i * 70}ms` }}>
                  <Link
                    href={tile.href}
                    className="flex h-16 items-center justify-center rounded-2xl bg-white/55 px-2 text-center text-sm font-medium text-muted-foreground shadow-xs ring-1 ring-primary/8 backdrop-blur-sm transition-colors hover:bg-brand-mint/70 hover:text-primary hover:ring-primary/20 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none sm:h-20"
                  >
                    {tile.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </HeroScene>

      <section id="vorhaben" className="scroll-mt-24">
        <div className="mx-auto max-w-6xl px-4 pt-8 pb-24 sm:px-6 sm:pt-12">
          <h2 className="text-4xl tracking-tight text-primary">Was kommt</h2>
          <p className="mt-3 max-w-2xl text-muted-foreground">
            Pathly wächst Schritt für Schritt – vom Register bis zur
            Unterstützung beim Übergang ins Berufsleben.
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

      {/* Abschluss: gleicher Schimmer wie oben, gespiegelt – läuft hinter die Fußzeile aus */}
      <section className="relative px-4 pt-16 pb-20 text-center sm:px-6 sm:pt-20 sm:pb-24">
        <Glow edge="bottom" />
        <h2 className="mx-auto max-w-2xl text-4xl tracking-tight text-balance text-primary sm:text-5xl">
          Bereit, deinen Weg zu <span className="text-brand-green">finden</span>?
        </h2>
        <p className="mx-auto mt-4 max-w-md text-muted-foreground">
          Durchsuche alle Hochschulen nach Name, Art, Trägerschaft und Bundesland.
        </p>
        <div className="mt-8 flex justify-center">
          <CtaButton href="/hochschulen">Hochschulen entdecken</CtaButton>
        </div>
      </section>
    </main>
  );
}
