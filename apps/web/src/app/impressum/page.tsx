import type { Metadata } from "next";
import { PROVIDER } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Impressum",
  robots: { index: false },
};

export default function ImpressumPage() {
  const address = (
    <>
      {PROVIDER.name}
      <br />
      {PROVIDER.street}
      <br />
      {PROVIDER.city}
      <br />
      {PROVIDER.country}
    </>
  );

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 sm:px-6">
      <h1 className="text-3xl tracking-tight text-primary">Impressum</h1>
      <div className="mt-8 space-y-6 [&_h2]:font-semibold [&_h2]:text-primary">
        <section>
          <h2>Angaben gemäß § 5 DDG</h2>
          <p className="mt-2">{address}</p>
        </section>
        <section>
          <h2>Kontakt</h2>
          <p className="mt-2">
            E-Mail:{" "}
            <a href={`mailto:${PROVIDER.email}`} className="underline underline-offset-4">
              {PROVIDER.email}
            </a>
          </p>
        </section>
        <section>
          <h2>Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV</h2>
          <p className="mt-2">{address}</p>
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
        <section>
          <h2>Haftung für Links</h2>
          <p className="mt-2">
            Diese Website enthält Links zu externen Websites, insbesondere zu
            Hochschulen und Landesministerien. Auf deren Inhalte haben wir
            keinen Einfluss; dafür ist der jeweilige Anbieter verantwortlich.
            Werden uns Rechtsverletzungen bekannt, entfernen wir den Link
            umgehend.
          </p>
        </section>
        <section id="quellen">
          <h2>Quellen und Lizenzen</h2>
          <ul className="mt-2 list-disc space-y-2 pl-5">
            <li>
              Hochschuldaten: offizielle Hochschullisten der Landesministerien
              der 16 Bundesländer; die jeweilige Quelle steht bei jeder
              Hochschule.
            </li>
            <li>
              Deutschlandkarte: „Map of Germany“ aus{" "}
              <a
                href="https://github.com/VictorCazanave/svg-maps"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-4"
              >
                svg-maps
              </a>{" "}
              von Victor Cazanave, lizenziert unter{" "}
              <a
                href="https://creativecommons.org/licenses/by/4.0/deed.de"
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-4"
              >
                CC BY 4.0
              </a>
              . Angepasst: Farben, Beschriftungen und Interaktion.
            </li>
          </ul>
        </section>
        <section>
          <h2>Verbraucherstreitbeilegung</h2>
          <p className="mt-2">
            Wir sind nicht bereit und nicht verpflichtet, an
            Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle
            teilzunehmen.
          </p>
        </section>
      </div>
    </main>
  );
}
