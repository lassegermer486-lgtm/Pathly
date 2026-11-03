// Einstieg: Der Lime-Creme-Schimmer sinkt beim Laden von oben herein und läuft
// hinter die schwebende Navigation. Kein Scroll-Festhalten – die Seite scrollt normal.
export function HeroScene({ children }: { children: React.ReactNode }) {
  return (
    <section className="relative -mt-20 flex min-h-svh flex-col justify-center overflow-hidden pt-28 pb-16">
      <div aria-hidden className="pointer-events-none absolute -inset-16 -z-10 animate-glow-drop">
        <div
          className="absolute inset-0 blur-[56px]"
          style={{
            background:
              "radial-gradient(ellipse 70% 45% at 45% 0%, var(--brand-lime) 30%, transparent 75%)," +
              "linear-gradient(160deg, var(--brand-lime) 15%, var(--brand-cream) 40%, transparent 60%)",
          }}
        />
      </div>
      {children}
    </section>
  );
}
