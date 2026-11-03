import type { Metadata } from "next";
import { PROVIDER } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Datenschutz",
  robots: { index: false },
};

// Text vor größerem Ausbau (Konten, Analyse, Newsletter) rechtlich prüfen lassen.
export default function DatenschutzPage() {
  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 sm:px-6">
      <h1 className="text-3xl font-bold tracking-tight">Datenschutzerklärung</h1>
      <div className="mt-8 space-y-6 text-foreground [&_h2]:font-semibold">
        <section>
          <h2>Verantwortlicher</h2>
          <p className="mt-2">
            {PROVIDER.name}, {PROVIDER.street}, {PROVIDER.city}
            <br />
            E-Mail:{" "}
            <a href={`mailto:${PROVIDER.email}`} className="underline underline-offset-4">
              {PROVIDER.email}
            </a>
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
            Supabase Inc. Beim reinen Besuch der Website werden dabei keine
            personenbezogenen Daten gespeichert.
          </p>
        </section>
        <section>
          <h2>Nutzerkonto</h2>
          <p className="mt-2">
            Ein Konto ist freiwillig; die Hochschulsuche funktioniert ohne. Wenn
            du ein Konto anlegst, verarbeiten wir deine E-Mail-Adresse, optional
            deinen Namen, ein verschlüsseltes (gehashtes) Passwort sowie
            Zeitpunkte von Registrierung und Anmeldung. Zur Bestätigung deiner
            E-Mail-Adresse und zum Zurücksetzen des Passworts schicken wir dir
            E-Mails. Rechtsgrundlage ist Art. 6 Abs. 1 lit. b DSGVO
            (Bereitstellung des Kontos).
          </p>
          <p className="mt-2">
            Die Kontodaten speichert unser Auftragsverarbeiter Supabase Inc. in
            seiner Datenbank. Du kannst dein Konto jederzeit unter „Mein Konto“
            selbst löschen; dabei werden die Kontodaten sofort entfernt.
          </p>
        </section>
        <section>
          <h2>Anmeldung mit Google</h2>
          <p className="mt-2">
            Wenn du „Mit Google anmelden“ wählst, wirst du zu Google Ireland
            Limited (Gordon House, Barrow Street, Dublin 4, Irland)
            weitergeleitet. Google übermittelt uns nach deiner Zustimmung deinen
            Namen, deine E-Mail-Adresse und ggf. dein Profilbild. Wir nutzen
            diese Daten nur für dein Konto. Rechtsgrundlage ist Art. 6 Abs. 1
            lit. b DSGVO. Für die Verarbeitung bei Google gilt dessen
            Datenschutzerklärung.
          </p>
        </section>
        <section>
          <h2>Cookies, Tracking und Schriftarten</h2>
          <p className="mt-2">
            Wir setzen keine Tracking- oder Marketing-Cookies und keine
            Analyse-Tools ein. Wenn du angemeldet bist, speichern wir technisch
            notwendige Cookies, die deine Sitzung enthalten; sie werden beim
            Abmelden gelöscht (§ 25 Abs. 2 TDDDG). Schriftarten werden von
            unserem eigenen Server ausgeliefert; es findet keine Verbindung zu
            Google statt.
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
