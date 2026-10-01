# Scraper-UI

Weboberfläche für den Hochschul-Scraper (`../projectpathly_registry_scraper`): Abruf starten, Fortschritt und Kennzahlen sehen, Bundesländer durchsehen, offene Duplikate entscheiden, Ergebnis als JSON speichern.

Die UI ist ein eigener Ordner und ändert **keine Datei des Scrapers**. Sie ruft dessen Funktionen auf und läuft nur lokal auf dem eigenen Rechner.

## Starten

Voraussetzung: Python 3.10 oder neuer. Im Repo-Wurzelordner:

```bash
./projectpathly_scraper_ui/start.sh
```

Beim ersten Aufruf richtet das Skript eine eigene Python-Umgebung ein (`projectpathly_scraper_ui/.venv`, etwa eine Minute). Danach im Browser öffnen: <http://localhost:8000>

Beenden mit `Strg+C` im Terminal.

Alternativ mit Docker (Docker Desktop muss laufen):

```bash
docker compose -f projectpathly_scraper_ui/docker-compose.yml up --build
```

## Bedienung

1. **Abruf starten** ruft die 16 Landesquellen ab (rund eine Minute, Schleswig-Holstein braucht davon etwa 30 Sekunden). Die Reiter füllen sich Land für Land.
2. Die Leiste darunter zeigt die Phase: Abrufen, Abgleichen, Prüfen, Entscheiden, Speichern.
3. Gibt es **offene Duplikate**, ist Speichern gesperrt. Im Reiter „Duplikate“ pro Paar „Zusammenführen“ oder „Getrennt lassen“ wählen, optional mit Begründung. Eine Entscheidung lässt sich zurücknehmen.
4. **Speichern** schreibt die Dateien (siehe unten). „JSON herunterladen“ liefert dasselbe Register als Datei.

Weitere Funktionen:

- **Optionen:** nur einzelne Bundesländer abrufen; Websites aller Hochschulen prüfen (dauert einige Minuten).
- **Letzten Abruf laden:** öffnet den zuletzt gespeicherten Abruf, ohne die Quellen erneut abzufragen. Praktisch zum Ausprobieren.
- **Erneut abrufen:** erscheint im Reiter eines Landes, dessen Abruf fehlgeschlagen ist.
- **Protokoll:** die Ausgabe des Scrapers, wie sie sonst im Terminal steht.
- Klick auf eine Tabellenzeile zeigt Standorte, Quellen und Hinweise.

## Datenbank

Nach dem Speichern erscheint der Knopf **„In Datenbank laden“**. Er schreibt das gespeicherte Register in die Supabase-Tabellen aus `supabase/migrations` (`universities`, `locations`, `sources`, `university_flags`, `university_aliases`) und protokolliert den Lauf in `import_runs`.

Einmalige Einrichtung:

1. Die Migrationen müssen im Supabase-Projekt eingespielt sein.
2. Vorlage kopieren: `cp projectpathly_scraper_ui/.env.example projectpathly_scraper_ui/.env`
3. Im Supabase-Dashboard auf „Connect“ klicken, die Adresse unter „Session pooler“ kopieren, in `.env` hinter `SUPABASE_DB_URL=` eintragen und `[YOUR-PASSWORD]` durch das Datenbank-Passwort ersetzen.

Die `.env` enthält ein Passwort mit Schreibrecht. Sie ist per `.gitignore` ausgeschlossen und darf nie eingecheckt werden. Ein Neustart der UI ist nach dem Anlegen nicht nötig.

Regeln des Imports:

- Alles läuft in einer Transaktion: entweder der komplette neue Stand oder gar nichts.
- Hochschulen werden über `registry_id` wiedererkannt. Ein zweiter Import aktualisiert, er verdoppelt nichts.
- Aus `universities` wird nie gelöscht. Fehlt eine Hochschule im Register, wird sie auf `is_listed = false` gesetzt.
- Standorte behalten ihre Datenbank-ID, solange Name und Adresse gleich bleiben.
- In die Datenbank darf nur ein gespeicherter, vollständiger Abruf aller 16 Länder. Bei einem Teilabruf würden sonst alle übrigen Hochschulen als nicht mehr gelistet markiert.
- Die Tabelle kennt bei Standorten nur `main`, `branch` und `unknown`. `campus`, `study_location` und `department` aus dem Scraper werden deshalb als `branch` gespeichert.

Ohne Oberfläche (zum Beispiel später in einer Pipeline) lädt derselbe Import die zuletzt gespeicherte Datei:

```bash
cd projectpathly_scraper_ui && .venv/bin/python -m scraper_ui.registry_import
```

## Was geschrieben wird

Alles landet im Scraper-Ordner, genau wie bei `python -m registry.master --save`:

| Wann | Datei | Im Repo versioniert |
|---|---|---|
| bei jeder Duplikat-Entscheidung | `config/overrides.yaml` | ja |
| Speichern | `data/master/university_registry.json` | nein |
| Speichern | `data/normalized/universities_de.json` | nein |
| Speichern | `data/reports/dedup_candidates.json`, `master_summary.json` | nein |
| Speichern | `config/id_registry.json` | ja |

Entscheidungen werden sofort in `config/overrides.yaml` eingetragen (mit Datum und Begründung als Kommentar), damit sie auch für spätere Läufe und die Kommandozeile gelten. Vorhandene Kommentare bleiben erhalten. Die beiden versionierten Dateien tauchen danach in `git status` auf und gehören mit committet.

Ein Abruf einzelner Länder überschreibt nie den vollständigen Datensatz, sondern schreibt `universities_<Kürzel>.json`.

## Zusammenspiel mit neuen Scraper-Versionen

Nur `scraper_ui/bridge.py` berührt Code des Scrapers. Dort wird beim Start geprüft, was die ausgecheckte Version kann:

| Funktion im Scraper | vorhanden | fehlt |
|---|---|---|
| `registry.run.scrape` | wird benutzt | Abruf über die Adapter direkt |
| `registry.states` | Länderliste von dort | eingebaute Liste |
| `registry.master` (Abgleich) | Duplikate, feste IDs, Hinweise | Rohliste ohne Abgleich, Reiter „Duplikate“ meldet das |

Unbekannte Werte (neuer Hochschultyp, neuer Hinweis) zeigt die Oberfläche unverändert an, unbekannte Felder erscheinen in der Detailansicht unter „Weitere Felder“. Getestet mit dem Stand von `main` (ohne Abgleich) und `Scraper-v1.2` (mit Abgleich).

Ändert eine neue Version etwas, worauf die UI angewiesen ist, schlägt `tests/test_bridge_real_scraper.py` fehl – dann ist `bridge.py` die Stelle zum Anpassen.

## Tests

```bash
projectpathly_scraper_ui/.venv/bin/pip install -r projectpathly_scraper_ui/requirements-dev.txt
```

```bash
cd projectpathly_scraper_ui && .venv/bin/python -m pytest -q tests
```

Die Tests brauchen kein Netz.

## Einstellungen

| Umgebungsvariable | Vorgabe | Zweck |
|---|---|---|
| `PATHLY_SCRAPER_DIR` | `../projectpathly_registry_scraper` | Ordner des Scrapers |
| `PATHLY_UI_PORT` | `8000` | Port |
| `SUPABASE_DB_URL` | leer | Verbindungsadresse der Datenbank; üblicherweise in `.env` statt in der Umgebung |
| `PATHLY_UI_HOST` | `127.0.0.1` | nur vom eigenen Rechner erreichbar; es gibt keinen Login, deshalb nicht öffentlich freigeben |

## Aufbau

```
projectpathly_scraper_ui/
├── start.sh                 Start ohne Docker
├── Dockerfile, docker-compose.yml
├── scraper_ui/
│   ├── bridge.py            einzige Verbindung zum Scraper
│   ├── runner.py            Laufzustand, Phasen, Entscheidungen, Speichern
│   ├── overrides_file.py    Einträge in config/overrides.yaml
│   ├── registry_import.py   Import in die Supabase-Datenbank
│   ├── app.py               HTTP-Schnittstelle
│   └── static/              Seite (HTML, CSS, JavaScript ohne Build-Schritt)
└── tests/
```
