import { Glow } from "@/components/glow";

// Einstieg: Der Lime-Creme-Schimmer sinkt beim Laden von oben herein und läuft
// hinter die schwebende Navigation. Kein overflow-hidden, damit er unten weich in den
// nächsten Abschnitt ausläuft (seitlich schneidet html { overflow-x: clip }).
export function HeroScene({ children }: { children: React.ReactNode }) {
  return (
    <section className="relative -mt-20 flex flex-col pt-36 pb-16 sm:pt-44">
      <Glow edge="top" className="animate-glow-drop" />
      {children}
    </section>
  );
}
