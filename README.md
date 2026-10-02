# ProjectPathly
Orientierungsplatform für Bildung und Karriere

## Ordnerstruktur

```
apps/
  web/              Web-App (Next.js)
  scraper-ui/       Weboberfläche zum Steuern der Scraper
scrapers/
  hochschulen/      Register aller deutschen Hochschulen aus Quellen der Bundesländer
supabase/
  migrations/       Datenbankschema
docs/               Feature-Katalog und weitere Dokumentation
```

Neue Scraper kommen als eigener Ordner unter `scrapers/<name>/` dazu und folgen
dem Aufbau von `scrapers/hochschulen/` (Python-Paket, `tests/`, `data/`,
`requirements.txt`, `README.md`). Rohabrufe in `data/raw/` werden nicht
versioniert.
