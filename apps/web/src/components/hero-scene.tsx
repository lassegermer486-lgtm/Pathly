import { Glow } from "@/components/glow";

// Einstieg: Der Lime-Creme-Schimmer sinkt beim Laden von oben herein und läuft
// hinter die schwebende Navigation. Kein Scroll-Festhalten – die Seite scrollt normal.
export function HeroScene({ children }: { children: React.ReactNode }) {
  return (
    <section className="relative -mt-20 flex min-h-svh flex-col justify-center overflow-hidden pt-28 pb-16">
      <Glow edge="top" className="animate-glow-drop" />
      {children}
    </section>
  );
}
