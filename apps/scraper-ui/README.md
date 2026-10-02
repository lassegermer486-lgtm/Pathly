# Scraper-UI

Weboberfläche für den Hochschul-Scraper (`../../scrapers/hochschulen`): Abruf starten, Fortschritt und Kennzahlen sehen, Bundesländer durchsehen, offene Duplikate entscheiden, Ergebnis als JSON speichern.

Die UI ist ein eigener Ordner und ändert **keine Datei des Scrapers**. Sie ruft dessen Funktionen auf und läuft nur lokal auf dem eigenen Rechner.

## Starten

Voraussetzung: Python 3.10 oder neuer. Im Repo-Wurzelordner:

```bash
./apps/scraper-ui/start.sh
```

Beim ersten Aufruf richtet das Skript eine eigene Python-Umgebung ein (`apps/scraper-ui/.venv`, etwa eine Minute). Danach im Browser öffnen: <http://localhost:8000>

Beenden mit `Strg+C` im Terminal.

Alternativ mit Docker (Docker Desktop muss laufen):

```bash
docker compose -f apps/scraper-ui/docker-compose.yml up --build
```

## Bedienung

1. **Abruf starten** ruft die 16 Landesquellen ab (rund eine Minute, Schleswig-Holstein braucht davon etwa 30 Sekunden). Die Reiter füllen sich Land für Land, zunächst ohne Abgleich.
2. Sind alle Länder da, läuft der Abgleich wie in der Pipeline des Scrapers (siehe unten). Die Leiste darunter zeigt die Phase: Abrufen, Abgleichen, Prüfen, Entscheiden, Speichern.
3. Gibt es **offene Duplikate**, ist Speichern gesperrt. Im Reiter „Duplikate“ pro Paar „Zusammenführen“ oder „Getrennt lassen“ wählen, optional mit Begründung. Eine Entscheidung lässt sich zurücknehmen.
4. **Speichern** schreibt die Dateien (siehe unten). „JSON herunterladen“ liefert das Register als Datei.

Weitere Funktionen:

- **Optionen:** nur einzelne Bundesländer abrufen; **Websites aller Hochschulen prüfen** (dauert einige Minuten). Ohne diese Option nimmt die UI die Ergebnisse der letzten Website-Prüfung aus `data/enriched/universities_de_urls.json`. Neue oder umbenannte Einträge gelten dann als „nicht geprüft“ und werden eher als mögliches Duplikat vorgelegt als automatisch zusammengeführt.
- **Letzten Abruf laden:** öffnet den zuletzt gespeicherten Abruf, ohne die Quellen erneut abzufragen. Praktisch zum Ausprobieren.
- **Erneut abrufen:** erscheint im Reiter eines Landes, dessen Abruf fehlgeschlagen ist. Als fehlgeschlagen gilt auch ein Land, aus dem 0 Hochschulen gelesen wurden, z. B. weil die Landesseite gerade eine Störungsseite zeigt. Solange ein Land fehlt, ist der Stand unvollständig und kommt nicht in die Datenbank.
- **Protokoll:** die Ausgabe des Scrapers, wie sie sonst im Terminal steht.
- Klick auf eine Tabellenzeile zeigt Standorte, Quellen und Hinweise.

## Datenbank

Nach dem Speichern erscheint der Knopf **„In Datenbank laden“**. Er schreibt das gespeicherte Register in die Supabase-Tabellen aus `supabase/migrations` (`universities`, `locations`, `sources`, `university_flags`, `university_aliases`) und protokolliert den Lauf in `import_runs`.

Das SQL dafür erzeugt der Scraper selbst (`registry.master.supabase_import`). Die UI führt genau das Skript aus, das beim Speichern auch als `data/master/supabase_import.sql` geschrieben wird. Knopf und `psql -f data/master/supabase_import.sql` laden die Datenbank also auf dieselbe Weise.

Einmalige Einrichtung:

1. Die Migrationen müssen im Supabase-Projekt eingespielt sein.
2. Vorlage kopieren: `cp apps/scraper-ui/.env.example apps/scraper-ui/.env`
3. Im Supabase-Dashboard auf „Connect“ klicken, die Adresse unter „Session pooler“ kopieren, in `.env` hinter `SUPABASE_DB_URL=` eintragen und `[YOUR-PASSWORD]` durch das Datenbank-Passwort ersetzen.

Die `.env` enthält ein Passwort mit Schreibrecht. Sie ist per `.gitignore` ausgeschlossen und darf nie eingecheckt werden. Ein Neustart der UI ist nach dem Anlegen nicht nötig.

Regeln des Imports:

- Alles läuft in einer Transaktion: entweder der komplette neue Stand oder gar nichts. Ein fehlgeschlagener Versuch wird in `import_runs` als `failed` vermerkt.
- Hochschulen werden über `registry_id` wiedererkannt. Ein zweiter Import aktualisiert, er verdoppelt nichts.
- Aus `universities` wird nie gelöscht. Fehlt eine Hochschule im Register, wird sie auf `is_listed = false` gesetzt.
- Standorte, Quellen und Hinweise der importierten Hochschulen werden ersetzt.
- Frühere IDs zusammengeführter Hochschulen landen in `university_aliases`.
- In die Datenbank darf nur ein gespeicherter, vollständiger Abruf aller 16 Länder. Bei einem Teilabruf würden sonst alle übrigen Hochschulen als nicht mehr gelistet markiert.

Ohne Oberfläche (zum Beispiel später in einer Pipeline) lädt derselbe Import den zuletzt gespeicherten Stand:

```bash
cd apps/scraper-ui && .venv/bin/python -m scraper_ui.registry_import
```

## Was geschrieben wird

Alles landet im Scraper-Ordner, in denselben Dateien wie bei `python -m registry.pipeline`:

| Wann | Datei |
|---|---|
| bei jeder Duplikat-Entscheidung | `data/master/overrides.yaml` |
| Speichern | `data/normalized/universities_de.json` (Abruf der Länder) |
| Speichern | `data/enriched/universities_de_urls.json` (mit Website-Prüfung) |
| Speichern | `data/master/universities_dedup.json`, `data/reports/dedup_report.json`, `review_report.md` |
| Speichern | `data/master/universities_de_master.json`, `university_metadata.json`, `locations.json`, `aliases.json`, `sources.json` |
| Speichern | `data/master/id_registry.json` (feste IDs) |
| Speichern | `data/reports/validation_report.json`, `data/master/supabase_import.sql` |

Entscheidungen werden sofort in `data/master/overrides.yaml` eingetragen (mit Datum und Begründung als Kommentar), damit sie auch für spätere Läufe und die Kommandozeile gelten. Vorhandene Kommentare bleiben erhalten.

Ein Abruf einzelner Länder schreibt nur `data/normalized/universities_<Kürzel>.json`. Er überschreibt weder den vollständigen Datensatz noch das Register.

## Zusammenspiel mit dem Scraper

Nur `scraper_ui/bridge.py` berührt Code des Scrapers. Sie führt die Schritte von `registry/pipeline.py` im Speicher aus:

| Schritt | Modul im Scraper | in der UI |
|---|---|---|
| Abruf | `registry.run` | Land für Land, mit Vorschau |
| Websites | `registry.enrichment.website_resolver` | mit Option „Websites prüfen“ live, sonst gespeicherte Ergebnisse |
| Agent | `registry.enrichment.agent_resolver` | nicht aus der UI (kostet API-Guthaben); gespeicherte Antworten werden über `data/enriched/` mitgenutzt |
| Duplikate | `registry.master.dedup` | Entscheidungen in `overrides.yaml` |
| Register | `registry.master.build` | Namen, Status, feste IDs; prüft dafür die Websites der wenigen Hochschulen, deren Namen sich in den Quellen widersprechen |
| Datenbank | `registry.master.supabase_import` | Knopf „In Datenbank laden“ |

Gleiche Eingabe, gleiches Ergebnis: Speichern in der UI schreibt dieselben Dateien wie die Pipeline auf der Kommandozeile.

Unbekannte Werte (neuer Hochschultyp, neuer Hinweis) zeigt die Oberfläche unverändert an, unbekannte Felder erscheinen in der Detailansicht unter „Weitere Felder“.

Ändert eine neue Scraper-Version etwas, worauf die UI angewiesen ist, schlägt `tests/test_bridge_real_scraper.py` fehl. Dann ist `bridge.py` die Stelle zum Anpassen.

## Tests

```bash
apps/scraper-ui/.venv/bin/pip install -r apps/scraper-ui/requirements-dev.txt
```

```bash
cd apps/scraper-ui && .venv/bin/python -m pytest -q tests
```

Die Tests brauchen kein Netz.

## Einstellungen

| Umgebungsvariable | Vorgabe | Zweck |
|---|---|---|
| `PATHLY_SCRAPER_DIR` | `../../scrapers/hochschulen` | Ordner des Scrapers |
| `PATHLY_UI_PORT` | `8000` | Port |
| `SUPABASE_DB_URL` | leer | Verbindungsadresse der Datenbank; üblicherweise in `.env` statt in der Umgebung |
| `PATHLY_UI_HOST` | `127.0.0.1` | nur vom eigenen Rechner erreichbar; es gibt keinen Login, deshalb nicht öffentlich freigeben |

## Aufbau

```
scraper-ui/
├── start.sh                 Start ohne Docker
├── Dockerfile, docker-compose.yml
├── scraper_ui/
│   ├── bridge.py            einzige Verbindung zum Scraper
│   ├── runner.py            Laufzustand, Phasen, Entscheidungen, Speichern
│   ├── overrides_file.py    Einträge in data/master/overrides.yaml
│   ├── registry_import.py   führt das Import-SQL des Scrapers in Supabase aus
│   ├── app.py               HTTP-Schnittstelle
│   └── static/              Seite (HTML, CSS, JavaScript ohne Build-Schritt)
└── tests/
```
