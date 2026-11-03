import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Datenschutz",
  robots: { index: false },
};

// TODO vor Livegang: Platzhalter ersetzen und Text rechtlich prüfen lassen.
export default function DatenschutzPage() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 sm:px-6">
      <h1 className="text-3xl font-bold tracking-tight">Datenschutzerklärung</h1>
      <div className="mt-8 space-y-6 text-foreground [&_h2]:font-semibold">
        <section>
          <h2>Verantwortlicher</h2>
          <p className="mt-2">
            [Vor- und Nachname bzw. Firmenname, Anschrift, E-Mail] – siehe
            Impressum.
          </p>
        </section>
        <section>
          <h2>Hosting</h2>
          <p className="mt-2">
            Diese Website wird bei Vercel Inc. (440 N Barranca Ave #4133,
            Covina, CA 91723, USA) gehostet. Beim Aufruf verarbeitet Vercel
            technisch notwendige Daten wie IP-Adresse, Zeitpunkt und
            aufgerufene Seite in Server-Logfiles. Rechtsgrundlage ist Art. 6
            Abs. 1 lit. f DSGVO (sicherer und stabiler Betrieb). Die
            Übermittlung in die USA erfolgt auf Grundlage des EU-US Data
            Privacy Framework bzw. von Standardvertragsklauseln.
          </p>
        </section>
        <section>
          <h2>Datenbank</h2>
          <p className="mt-2">
            Die angezeigten Hochschuldaten laden wir aus einer Datenbank bei
            Supabase Inc. Dabei werden keine personenbezogenen Daten von
            Besucherinnen und Besuchern gespeichert.
          </p>
        </section>
        <section>
          <h2>Cookies, Tracking und Schriftarten</h2>
          <p className="mt-2">
            Wir setzen keine Tracking- oder Marketing-Cookies und keine
            Analyse-Tools ein. Schriftarten werden von unserem eigenen Server
            ausgeliefert; es findet keine Verbindung zu Google statt.
          </p>
        </section>
        <section>
          <h2>Deine Rechte</h2>
          <p className="mt-2">
            Du hast das Recht auf Auskunft, Berichtigung, Löschung,
            Einschränkung der Verarbeitung, Datenübertragbarkeit und
            Widerspruch sowie das Recht, dich bei einer
            Datenschutz-Aufsichtsbehörde zu beschweren.
          </p>
        </section>
      </div>
    </main>
  );
}
