import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Impressum",
  robots: { index: false },
};

// TODO vor Livegang: Platzhalter in [eckigen Klammern] durch echte Angaben ersetzen.
export default function ImpressumPage() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 sm:px-6">
      <h1 className="text-3xl font-bold tracking-tight">Impressum</h1>
      <div className="mt-8 space-y-6 text-foreground [&_h2]:font-semibold">
        <section>
          <h2>Angaben gemäß § 5 DDG</h2>
          <p className="mt-2">
            [Vor- und Nachname bzw. Firmenname]
            <br />
            [Straße und Hausnummer]
            <br />
            [PLZ Ort]
          </p>
        </section>
        <section>
          <h2>Kontakt</h2>
          <p className="mt-2">E-Mail: [kontakt@pathly.info]</p>
        </section>
        <section>
          <h2>Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV</h2>
          <p className="mt-2">[Vor- und Nachname, Anschrift wie oben]</p>
        </section>
        <section>
          <h2>Haftung für Inhalte</h2>
          <p className="mt-2">
            Die Angaben zu Hochschulen stammen aus öffentlich zugänglichen,
            offiziellen Quellen der Bundesländer. Wir prüfen sie sorgfältig,
            übernehmen aber keine Gewähr für Richtigkeit, Vollständigkeit und
            Aktualität. Maßgeblich sind die Angaben der jeweiligen Hochschule.
          </p>
        </section>
      </div>
    </main>
  );
}
