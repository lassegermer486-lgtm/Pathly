# Hochschulregister v1.3 – Internationale Online-Hochschulen (Europa + USA)

Stand: 02.10.2026. Recherche und Umsetzungsvorschlag für Phase C.

Gesucht sind **internationale Hochschulen ohne deutschen Campus, an denen ein
vollständiges Studium online aus Deutschland möglich ist** (Spec §C1–C4).
Deutsche Hochschulen kommen weiter aus den 16 Landesquellen und werden nicht
erneut gesucht (§C2).

Grundsatz für beide Quellen: **Discovery ≠ Bestätigung.** Eine Quelle macht
eine Hochschule nur zum Kandidaten (`online_de_status = review`). Bestätigt
wird nur mit Beleg.

| | Europa | USA |
|---|---|---|
| Discovery-Quelle | ETER / EHESO (EU-Kommission) | IPEDS (U.S. Department of Education, NCES) |
| Online-Signal | `Distance education institution` = 2 | `DISTNCED` = 1 **und** ≥ 90 % reine Online-Studierende |
| Legitimität | Meldung durch die nationale Behörde | Title-IV-Teilnahme (`PSET4FLG` = 1), Akkreditierung über DAPIP |
| Kandidaten (strenger Filter) | 25 (Stand 2021/22) | 45 |

---

## 1. Europa: ETER / EHESO

### 1.1 Aktualität der Daten

| Version | Referenzjahr | Zugang | Lizenz | Reproduzierbar |
|---|---|---|---|---|
| Zenodo-Dump `ETER_fullDump_26032024.csv` ([DOI 10.5281/zenodo.10879501](https://zenodo.org/records/10879501)) | bis 2021/22 | Direkt-Download, kein Konto | CC BY 4.0 | ja (DOI, fester Dateiinhalt) |
| EHESO-Microdaten 2022/23 (veröffentlicht 24.03.2025) | 2022/23 | Web-App / API | nicht ausdrücklich angegeben | nur als eigener Snapshot |
| **EHESO-Microdaten 2023/24 (verfügbar seit 04.05.2026)** | **2023/24** | API 4.0 mit Login (JWT) | nicht ausdrücklich angegeben | nur als eigener Snapshot |

- Auf Zenodo ist der Dump vom März 2024 die neueste Version (Abfrage der
  Zenodo-API vom 02.10.2026).
- ETER heißt inzwischen EHESO. Die alte Website `eter-project.com` leitet
  auf die Plattform der EACEA weiter.
- API: `https://eter-project.com/api/4.0/users/login` (Login, Token 12 h gültig),
  dann `…/api/4.0/HEIs/query/flattened` mit einem Mongo-Filter, z. B.
  `{"BAS.REFYEAR.v": 2023}`. Variablen-Codes stehen in der
  Korrespondenztabelle des Zenodo-Dumps.

**Empfehlung:** Der Adapter liest beide Formate (dieselben Variablen). Fest
gepinnt wird zunächst der Zenodo-Dump: offen, mit DOI, ohne Konto,
SHA-256 `d14155ddc56b0488…`. Sobald ein EHESO-Konto besteht, kommt ein
API-Snapshot 2023/24 als eigene, gepinnte Datei dazu (Abrufdatum, SHA-256,
Referenzjahr in der Provenienz). Wichtig ist: Ein Kandidat entsteht nur aus
gepinnten Dateien, nie aus einem Live-Abruf ohne Snapshot.

### 1.2 Die Fernstudium-Variable

| | |
|---|---|
| Label | `Distance education institution` |
| API-Code | `STUD.DISTEDUINST` (Korrespondenztabelle des Dumps) |
| Definition | ETER-Handbuch 2025, Abschnitt 5.6.4, wortgleich mit Handbuch 2022, Abschnitt 6.8.4 |
| Bedeutung | „institutions in which distance education represents a substantial component of the educational offer“; Fernstudium = Studierende kommen nicht regelmäßig auf den Campus, außer zu Workshops oder kurzen Seminaren; Blended Learning mit wesentlichen Präsenzanteilen zählt nicht |
| `0` | „no or limited amount of distance education (<20% of the students in distance programmes)“ |
| `1` | „a substantial share of distance education“ (Beispiel: Anadolu University) |
| `2` | „mostly distance education (>90% of the student in distance programmes)“ (Beispiele: FernUniversität Hagen, UK Open University) |
| Sonderwerte | `m` (fehlt), `c` (vertraulich) u. a. |
| Datenquelle | nationale Statistikämter, optional nationale Experten |
| Standort | Fernhochschulen zählen zum Land ihres Hauptsitzes, unabhängig vom Wohnort der Studierenden (passt zu §C12) |

**Qualität:** Die Variable ist ein Kandidaten-Signal und kein Beweis.
- Zypern meldet 2021 *alle* Universitäten mit `2`, auch die
  Präsenzuniversität Cyprus University of Technology. In den Länder-Metadaten
  steht trotzdem „No departure from ETER definition“.
- Albanien meldet 2016 alle Universitäten mit `2`.

### 1.3 Discovery-Filter Europa

```text
Country Code ≠ DE                      (deutsche Hochschulen kommen aus den Landesquellen)
Distance education institution = 2   (strenge Gruppe, > 90 %)
Wert aus dem jüngsten Referenzjahr mit Angabe (0/1/2; fehlend „m“ wird übersprungen),
dieses Referenzjahr ≥ 2019
Institutional website vorhanden
```

Ergebnis mit dem Zenodo-Dump: **25 Kandidaten**. Die Gruppe `1` (21 weitere,
z. B. die italienischen Telematik-Universitäten) folgt erst, wenn die
Architektur steht.

| Land | Hochschule | Website | ETER ID |
|---|---|---|---|
| AT | Ferdinand Porsche Fern FH-Studiengänge | http://www.fernfh.at/ | AT0061 |
| CH | Swiss Distance Education University | http://www.fernuni.ch | CH0035 |
| CY | American College | http://www.ac.ac.cy | CY0014 |
| CY | Cyprus University of Technology ⚠ | http://www.cut.ac.cy | CY0003 |
| CY | European University - Cyprus | http://www.euc.ac.cy | CY0006 |
| CY | Frederick University | http://www.frederick.ac.cy | CY0005 |
| CY | Neapolis University | http://www.nup.ac.cy | CY0038 |
| CY | Open University of Cyprus | http://www.ouc.ac.cy | CY0002 |
| CY | University of Central Lancashire - Cyprus | http://www.uclancyprus.ac.cy | CY0042 |
| CY | University of Nicosia | http://www.unic.ac.cy | CY0004 |
| ES | International University Isabel I de Castilla | http://www.ui1.es | ES0063 |
| ES | International University of La Rioja (UNIR) | http://www.unir.net | ES0064 |
| ES | National University of Distance Education (UNED) | http://www.uned.es | ES0067 |
| ES | Open University of Catalonia (UOC) | http://www.uoc.edu | ES0076 |
| ES | Open University of Madrid (UDIMA) | http://www.udima.es | ES0049 |
| ES | Valencian International University | https://www.universidadviu.es/ | ES0075 |
| GR | Hellenic Open University | http://www.eap.gr/ | GR0001 |
| HR | Rochester Institute of Technology Croatia ⚠ | http://www.croatia.rit.edu/ | HR0025 |
| MT | Future Focus | https://futurefocus.com.mt/ | MT0009 |
| MT | Pegaso International | https://pegasointernational.eu/ | MT0007 |
| MT | Triagon Academy | https://www.triagon.mt/de/ | MT0010 |
| NL | Open University of the Netherlands | http://www.ou.nl/ | NL0014 |
| PT | Open University of Portugal | http://www.uab.pt | PT0015 |
| TR | Anadolu University | https://www.anadolu.edu.tr/en | TR0012 |
| UK | The Open University | http://www.open.ac.uk/ | UK0088 |

⚠ = Online-Flag fraglich (Präsenzhochschule). Diese Einträge bleiben
Kandidaten in `review`; ETER-Angaben werden nicht korrigiert.
ETER schreibt `UK`; beim Import wird daraus ISO `GB`.

---

## 2. USA: IPEDS

### 2.1 Aktualität der Daten (geprüft am 02.10.2026 auf nces.ed.gov)

| Datei | Inhalt | Zeitraum | Release | SHA-256 (Anfang) |
|---|---|---|---|---|
| `HD2024` | Verzeichnis: Name, Website, Status, Träger, Abschlussniveau, Title IV, OPEID | Erhebung 2024-25 | Release 1, Sept. 2025 | `d98425c123d7c0e8` |
| `IC2024` | Institutionelle Merkmale inkl. Fernstudium | Erhebung 2024-25 | Provisional Release 1, Sept. 2025 | `924f04f0afd95363` |
| `EFFY2024_DIST` | 12-Monats-Einschreibung nach Fernstudium-Status | 07/2023–06/2024 | Provisional, Sept. 2025 | `0d7e66e950c5f7a6` |
| `EF2023A_DIST` | Herbst-Einschreibung nach Fernstudium-Status und **Wohnort** | Herbst 2023 | Provisional | `82cf7c0db273ba3f` |

`HD2025`, `IC2025` und `EF2024A_DIST` gibt es noch nicht (HTTP 404).
Download-Muster: `https://nces.ed.gov/ipeds/datacenter/data/<Datei>.zip`,
Wörterbücher als `<Datei>_Dict.zip`. IPEDS-Daten sind Bundesdaten der USA
und frei nutzbar.

### 2.2 Fernstudium-Variablen (aus den offiziellen Wörterbüchern)

| Datei | Variable | Bedeutung (Original) | bildet institutionelle Online-Ausrichtung ab? |
|---|---|---|---|
| IC2024 | **`DISTNCED`** | „Are all the programs at your institution offered completely via distance education?“ (1 = Yes: 74 Hochschulen, 2 = No: 5.819, −2 = n/a: 70) | **ja**, direkt: Selbstauskunft „ausschließlich online“ |
| IC2024 | `DISTPGS` | Distance education programs offered (1 = ja: 2.800) | nein, nur „bietet irgendein Online-Programm an“ |
| IC2024 | `DSTNUGP` / `DSTNGP` | Online-Programme auf Bachelor- / Master-Ebene | nein, zu breit |
| IC2024 | `DISTCRS`, `DSTNUGC`, `DSTNGC`, `DSTNCED1–3` | Online-Kurse bzw. -Angebote | nein |
| EFFY2024_DIST | `EFYDETOT`, **`EFYDEEXC`**, `EFYDESOM`, `EFYDENON` (Ebene `EFFYDLEV = 1`, alle Studierenden) | alle / ausschließlich online / teilweise online / gar nicht online, 12 Monate | **ja**, gemessen: Anteil `EFYDEEXC / EFYDETOT` |
| EF2023A_DIST | **`EFDEEX4`** | „Students enrolled exclusively in distance education courses … residing outside the U.S.“ | **Hinweis auf Zugang aus dem Ausland** (nicht auf Deutschland) |
| HD2024 | `CYACTIVE`, `PSET4FLG`, `DEGGRANT`, `HLOFFER`, `CONTROL`, `WEBADDR`, `OPEID` | aktiv, Title IV, verleiht Abschlüsse, höchstes Niveau, Träger, Website, OPE-ID | Filter / Identität |

Definition „distance education program“ in IPEDS: Alle für den Abschluss
nötigen Kurse lassen sich online absolvieren. Präsenzpflichten nur für
Orientierung, Prüfungen oder Beratung schließen das nicht aus.

### 2.3 Lassen sich „ausschließlich / überwiegend online“-Hochschulen erkennen?

Ja, auf zwei unabhängigen Wegen:

| Filter (jeweils + aktiv, Title IV, verleiht Abschlüsse, höchstens ≥ Bachelor) | Anzahl |
|---|---|
| A: `DISTNCED = 1` (Selbstauskunft „alle Programme vollständig online“) | 51 |
| B: ≥ 90 % ausschließlich online Studierende (12 Monate 2023/24, ≥ 100 Studierende) | 90 |
| **A ∩ B** | **45** |
| A ∩ B mit Studierenden außerhalb der USA (`EFDEEX4 > 0`) | 34 |
| nur B (z. B. University of Phoenix, SNHU, Purdue Global, Penn State World Campus, 8 Strayer- und 4 DeVry-Einheiten) | 45 |

Beobachtungen:
- B allein bringt viele Filial-Einheiten derselben Marke (Strayer, DeVry,
  Bryan), die die Dedup erst zusammenführen müsste. A ∩ B vermeidet das
  weitgehend.
- `EFDEEX4` ist ein gutes **Prioritätssignal**, aber kein Filter: Western
  Governors University hat 0 Auslands-Studierende und nimmt tatsächlich nur
  US-Einwohner auf. Walden hat ebenfalls 0, das muss aber nicht „nicht
  zugänglich“ bedeuten.

### 2.4 Discovery-Filter USA (Vorschlag)

```text
HD2024:  CYACTIVE = 1, PSET4FLG = 1, DEGGRANT = 1, HLOFFER ≥ 5 (Bachelor oder höher)
IC2024:  DISTNCED = 1
EFFY2024_DIST (EFFYDLEV = 1): EFYDEEXC / EFYDETOT ≥ 0,90 und EFYDETOT ≥ 100
```

Ergebnis: **45 Kandidaten**, alle `review`. `EFDEEX4` (Studierende im
Ausland) wird als Evidenz-Signal gespeichert und sortiert die Review-Liste;
es filtert nicht.

<details>
<summary>Die 45 Kandidaten</summary>

| Hochschule | Staat | Träger | höchster Abschluss | Studierende 2023/24 | davon im Ausland (Herbst 2023) | UNITID |
|---|---|---|---|---|---|---|
| Abilene Christian University-Undergraduate Online | TX | privat, gemeinnützig | Bachelor | 1.536 | 72 | 497037 |
| Abraham Lincoln University | CA | privat, gewinnorientiert | Doktor | 208 | 4 | 488031 |
| America Evangelical University | CA | privat, gemeinnützig | Doktor | 329 | 0 | 490081 |
| American College of Healthcare Sciences | OR | privat, gewinnorientiert | Doktor | 1.574 | 15 | 443599 |
| American InterContinental University System | AZ | privat, gewinnorientiert | Doktor | 23.926 | 354 | 445027 |
| American Public University System | WV | privat, gewinnorientiert | Doktor | 95.158 | 58 | 449339 |
| Amridge University | AL | privat, gemeinnützig | Doktor | 861 | 0 | 100690 |
| Arizona State University Digital Immersion | AZ | öffentlich | Doktor | 98.316 | 2518 | 483124 |
| Bridges Christian College | LA | privat, gemeinnützig | Doktor | 179 | 13 | 497408 |
| Bryant & Stratton College-Online | NY | privat, gemeinnützig | Bachelor | 16.061 | 0 | 480091 |
| California Intercontinental University | SD | privat, gewinnorientiert | Doktor | 883 | 125 | 485546 |
| Capella University | MN | privat, gewinnorientiert | Doktor | 81.047 | 162 | 413413 |
| Catholic International University | WV | privat, gemeinnützig | Master | 286 | 6 | 475398 |
| Charter Oak State College | CT | öffentlich | Master | 2.540 | 5 | 128780 |
| City Vision University | MO | privat, gemeinnützig | Master | 422 | 12 | 457697 |
| Claremont Lincoln University | CA | privat, gemeinnützig | Master | 339 | 0 | 488387 |
| Colorado State University Global | CO | öffentlich | Master | 15.502 | 3 | 476975 |
| Columbia Southern University | AL | privat, gewinnorientiert | Doktor | 30.425 | 547 | 450933 |
| Crestpoint University | AZ | privat, gewinnorientiert | Master | 618 | 3 | 461023 |
| Evangel University-College of Online Learning | MO | privat, gemeinnützig | Bachelor | 349 | 1 | 497824 |
| Excelsior University | NY | privat, gemeinnützig | Post-Master | 18.823 | 197 | 196680 |
| Florida Institute of Technology-Online | FL | privat, gemeinnützig | Master | 1.835 | 26 | 480569 |
| Frontier Nursing University | KY | privat, gemeinnützig | Doktor | 3.483 | 2 | 156727 |
| Johnson & Wales University-Online | RI | privat, gemeinnützig | Doktor | 3.765 | 15 | 460349 |
| Lexington Theological Seminary | KY | privat, gemeinnützig | Doktor | 109 | 0 | 157207 |
| Lionel University | CA | privat, gewinnorientiert | Master | 654 | 1 | 485519 |
| Los Angeles Pacific University | CA | privat, gemeinnützig | Master | 2.884 | 0 | 474863 |
| Martinsburg College | WV | privat, gewinnorientiert | Post-Bacc. | 4.870 | 57 | 487977 |
| Midwives College of Utah | UT | privat, gemeinnützig | Master | 362 | 8 | 480985 |
| National American University-Rapid City | SD | privat, gewinnorientiert | Doktor | 1.660 | 27 | 219204 |
| Nazarene Bible College | CO | privat, gemeinnützig | Bachelor | 884 | 20 | 127714 |
| Northcentral University | CA | privat, gemeinnützig | Doktor | 12.994 | 89 | 444130 |
| Reach University | CA | privat, gemeinnützig | Master | 1.768 | 0 | 497480 |
| Relay Graduate School of Education | NY | privat, gemeinnützig | Master | 2.477 | 0 | 475033 |
| Sessions College for Professional Design | AZ | privat, gewinnorientiert | Bachelor | 279 | 2 | 475839 |
| South University-Savannah Online | GA | privat, gewinnorientiert | Doktor | 15.044 | 22 | 475121 |
| Taft University System | CO | privat, gewinnorientiert | Doktor | 532 | 0 | 454689 |
| University of Arkansas Grantham | AR | öffentlich | Master | 5.464 | 136 | 442569 |
| University of Florida-Online | FL | öffentlich | Bachelor | 6.778 | 164 | 484473 |
| University of New Hampshire College of Professional Studies Online | NH | öffentlich | Master | 2.257 | 1 | 183257 |
| University of Wisconsin-Milwaukee Flex | WI | öffentlich | Bachelor | 928 | 2 | 491288 |
| University of Wisconsin-Parkside Flex | WI | öffentlich | Bachelor | 219 | 1 | 491297 |
| Veritas Baptist College | IN | privat, gemeinnützig | Doktor | 317 | 19 | 482228 |
| Walden University | MN | privat, gewinnorientiert | Doktor | 72.855 | 0 | 125231 |
| Western Governors University | UT | privat, gemeinnützig | Post-Master | 282.150 | 0 | 433387 |

</details>

Hinweis zur Identität: Einige UNITIDs sind Online-Einheiten großer
Präsenzuniversitäten (ASU Digital Immersion, UF Online, UW Flex). In IPEDS
sind sie eigene Einheiten mit eigener Website. Die Dedup behandelt sie wie
jede andere Quelle; ein Abgleich mit der Mutteruniversität ist nicht nötig,
da diese nicht im Register steht.

### 2.5 Anerkennung / Akkreditierung (USA)

| Quelle | Rolle |
|---|---|
| **IPEDS `PSET4FLG = 1`** (Title-IV-Teilnahme) | deterministischer Filter: Title-IV-Teilnahme setzt Akkreditierung durch eine vom U.S. Department of Education anerkannte Agentur voraus |
| **DAPIP** (Database of Accredited Postsecondary Institutions and Programs, [ope.ed.gov/dapip](https://ope.ed.gov/dapip/)) | offizieller Akkreditierungsnachweis je Hochschule (Akkreditierer, Status); Abgleich über `OPEID`; Datendateien über die Web-Oberfläche („Download Data Files“), die API dahinter ist nicht dokumentiert |
| anabin (KMK/ZAB, Status H+) | Beleg für die Anerkennung in Deutschland, manuell pro Hochschule |

---

## 3. Gemeinsamer Vorschlag

### 3.1 Datenfluss (eine Registry, kein Parallelsystem)

```text
16 Landesadapter ──► data/normalized/universities_de.json        (unverändert)
ETER  ─┐
IPEDS ─┴─► registry.international ──► data/normalized/universities_intl.json   (neu)
                                       data/reports/international_online_discovery.json

website_resolver --in …_intl.json --out data/enriched/universities_intl_urls.json   (keine Codeänderung)
agent_resolver   --in data/enriched/universities_intl_urls.json                     (keine Codeänderung)

dedup:  liest beide enriched-Dateien  ──► eine universities_dedup.json
master: eine Master-Registry (+ country, market_access, online_de_*)
supabase: ein Import
```

### 3.2 Datenmodell

Normalisierter Kandidat (gleiche Form wie die Landesdatensätze, plus Discovery-Block):

```json
{
  "name": "Universitat Oberta de Catalunya",
  "country": "ES",
  "state": "INTL-ETER",
  "institution_type": "unknown",
  "ownership": "private",
  "recognition_status": "unknown",
  "official_url": "http://www.uoc.edu",
  "locations": [{"city": "Barcelona", "country": "ES", "location_type": "main"}],
  "source": {
    "authority": "European Commission – ETER/EHESO",
    "source_url": "https://zenodo.org/records/10879501",
    "source_type": "dataset",
    "dataset_version": "ETER_fullDump_26032024",
    "dataset_sha256": "d14155ddc56b0488…",
    "reference_year": 2021,
    "retrieved_at": "2026-10-02T…"
  },
  "discovery": {
    "source": "eter",
    "external_ids": {"eter": "ES0076", "ror": "…", "whed": "…"},
    "signals": {"distance_education_institution": 2}
  }
}
```

- `state` = Quellen-Kennung (`INTL-ETER`, `INTL-IPEDS`). Damit bleiben
  `record_key` („Quelle|Name“), `overrides.yaml` und `listed_by` ohne
  Codeänderung eindeutig.
- `country` = Heimatland (ISO-3166-1 alpha-2; ETER `UK` → `GB`, IPEDS → `US`).
- Master-Zeile, zusätzlich zu allen bisherigen Feldern:

| Feld | Werte | Deutsche Hochschule | Internationaler Kandidat |
|---|---|---|---|
| `country` | ISO-2 | `DE` (wie bisher) | Heimatland |
| `german_physical_presence` | true/false/null | aus Phase B | `false`, Basis `no_german_source_listing` |
| `online_de_status` | `confirmed` / `not_available` / `review` / `not_assessed` | `not_assessed` (§C2) | `review` bis zur Entscheidung |
| `online_de_basis`, `online_de_evidence_url` | Text / URL | – | aus der Entscheidung |
| `market_access` | Liste aus `physical_de`, `online_de` | `["physical_de"]` wenn Präsenz bestätigt | `["online_de"]` erst bei `confirmed` |
| `external_ids` | `{"eter": …, "ipeds_unitid": …, "opeid": …, "ror": …}` | – | aus der Quelle |

### 3.3 Evidenz-Modell und `online_de_status`

Gleiches Muster wie die Präsenz in Phase B: `data/master/online_de_decisions.yaml`,
Schlüssel ist die stabile `registry_id`.

```yaml
decisions:
  - registry_id: PTH-DE-XXXXXXXX
    status: confirmed            # confirmed | not_available | review
    degree_evidence_url: https://…   # Pflicht bei confirmed: vollständiger Online-Abschluss
    eligibility_evidence_url: https://…  # Pflicht bei confirmed/not_available: Zulassung aus DE bzw. Länderbeschränkung
    recognition_evidence_url: https://…  # optional: anabin H+, DAPIP, DEQAR
    checked_at: 2026-10-02
    note: ""
```

- `confirmed` nur mit **beiden** Belegen (§C4: vollständiges Online-Studium
  und Zugang aus Deutschland).
- „International students welcome“ allein reicht nicht, wenn anderswo
  Länderbeschränkungen stehen (§C8).
- Agent-Vorschläge (§D7) sind später möglich, aber nur als Vorschlag mit
  Beleg-URL in derselben Datei, nie als direkte Entscheidung.

### 3.4 Provenienz – die vier Fragen aus §D6

| Frage | Antwort steht in |
|---|---|
| Woher kommt die Hochschule? | `sources.json` (Datensatz, Version, SHA-256, Referenzjahr, Satz-ID) |
| Warum aufgenommen? | `discovery.signals` (z. B. `distance_education_institution = 2`, `DISTNCED = 1`, Online-Anteil 1,00) |
| Warum (keine) deutsche Präsenz? | `presence_basis` (Phase B) |
| Warum online aus Deutschland? | `online_de_basis` + Beleg-URLs aus `online_de_decisions.yaml` |

### 3.5 Nötige Änderungen am bestehenden Code (D bleibt oberste Priorität)

| Stelle | Änderung | Wirkung auf deutsche Daten |
|---|---|---|
| neu: `registry/international/` (`eter.py`, `ipeds.py`, `run.py`), `registry/international_sources.yaml` | Discovery aus gepinnten Dateien, Cache in `data/source_cache/INTL-*` | keine |
| `registry/pipeline.py` | Schritt `international` nach `discovery`; Resolver-Läufe für die intl-Dateien | keine |
| `registry/master/dedup.py` | `--in` nimmt mehrere Dateien (Default unverändert) | keine (gleiche Eingabe → gleiche Ausgabe) |
| `registry/master/build.py` | `country` aus den Datensätzen statt fest `DE`; `market_access`, `online_de_*`, `external_ids` anhängen | Werte bleiben `DE`, nur neue Felder |
| `registry/master/presence.py` | nur `DE-*`-Listungen zählen als deutsche Beobachtung | keine (heute nur `DE-*`) |
| `registry/reliability.py` | `INTL-ETER`/`INTL-IPEDS` als zusätzliche Quellen mit Drift-Prüfung | 16 Länder unverändert |
| `registry/master/supabase_import.py` + Migration | `country` aus den Daten; Spalten `market_access text[]`, `online_de_status`, `online_de_basis`, `online_de_evidence_url`, `external_ids jsonb` | keine |
| `registry/utils/validation.py` | **unverändert** (gilt nur für Landesadapter); intl hat eigene Validierung | keine |

IDs: Neue Hochschulen bekommen neue `PTH-DE-…`-IDs über die bestehende
`IdRegistry` (§D5). Die Mitgliedsschlüssel der 435 bestehenden Hochschulen
ändern sich nicht, ihre IDs bleiben also gleich. Das prüft
`tests/test_stable_ids.py` bei jedem Lauf.

### 3.6 Erwartete Kandidatenzahlen (erste Iteration)

| Quelle | Filter | Kandidaten | danach `confirmed` |
|---|---|---|---|
| ETER (Zenodo, 2021/22) | Wert 2, ≠ DE, Referenzjahr ≥ 2019 | 25 | 0 (alle `review`) |
| IPEDS (2024-25 / 2023-24) | A ∩ B | 45 | 0 (alle `review`) |
| **zusammen** | | **70** | |

Erweiterungen in einem späteren Schritt: ETER-Wert `1` (+21), EHESO
2023/24, IPEDS „nur B“ (+45, viele Filialen).

---

## Quellen

- [ETER – Full dataset (csv; March 26th, 2024), Zenodo](https://zenodo.org/records/10879501)
- [ETER/EHESO Handbook 2025, Zenodo (CC BY 4.0)](https://zenodo.org/records/21126398), Abschnitt 5.6.4
- [ETER Handbook 2022](https://eter-project.com/wp-content/uploads/2022/10/ETERIV_Handbook_2022.pdf), Abschnitt 6.8.4
- [EHESO Microdata 2022/2023](https://national-policies.eacea.ec.europa.eu/eheso/news/eheso-microdata-for-the-academic-year-20222023-now-online)
- [EHESO Microdata 2023/2024 ab 4. Mai](https://national-policies.eacea.ec.europa.eu/eheso/news/eheso-microdata-for-the-academic-year-20232024-available-from-4-may)
- [EHESO Microdata Access](https://national-policies.eacea.ec.europa.eu/eheso/micro-data-access)
- [EHESO/ETER API – General API Information](https://eter-project.com/data/technical-documentation/general-api-information/), [API-Beispiel (R)](https://eter-project.com/data/technical-documentation/api-request-using-r/)
- [IPEDS – Distance Education in IPEDS](https://nces.ed.gov/ipeds/use-the-data/distance-education-in-ipeds); Datendateien und Wörterbücher: `https://nces.ed.gov/ipeds/datacenter/data/`
- [DAPIP](https://ope.ed.gov/dapip/)
- [DEQAR – Provider Data](https://docs.deqar.eu/stable/institution_data/), [Web API](https://docs.deqar.eu/stable/web_api_intro/)
- [anabin – Anerkennung ausländischer Hochschulen](https://anabin.kmk.org/rechercheanleitung-hochschule)
- [Open University – Study with The Open University](https://www.open.edu/openlearn/about-openlearn/study)
