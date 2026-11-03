import { cn } from "@/lib/utils";

// Lime-Creme-Schimmer der Marke. "top" hängt von oben herab (Hero),
// "bottom" ist das Spiegelbild (um 180° gedreht) und steigt von unten rechts auf.
// Liegt hinter dem Inhalt; der Elternabschnitt braucht `relative`.
export function Glow({ edge = "top", className }: { edge?: "top" | "bottom"; className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute -inset-x-16 -z-10",
        edge === "top" ? "-top-16 -bottom-16" : "-top-16 -bottom-40 rotate-180",
        className
      )}
    >
      <div
        className="absolute inset-0 blur-[56px]"
        style={{
          background:
            "radial-gradient(ellipse 70% 45% at 45% 0%, var(--brand-lime) 30%, transparent 75%)," +
            "linear-gradient(160deg, var(--brand-lime) 15%, var(--brand-cream) 40%, transparent 60%)",
        }}
      />
    </div>
  );
}
