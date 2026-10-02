-- =====================================================================
-- Hochschulregister v1.3: internationale Online-Hochschulen, Marktzugang
--
-- Nur neue Spalten, nichts wird gelöscht oder umbenannt. Bestehende
-- Zeilen gelten bis zum nächsten Import als "not_assessed" ohne
-- Marktzugang. Reihenfolge: 20261002120000_university_presence.sql,
-- dann diese Migration, dann der v1.3-Import.
--
-- universities.country war schon vorhanden (Vorgabe 'DE'); ab v1.3 ist
-- es das Heimatland, z. B. 'ES' oder 'US'. registry_id bleibt PTH-DE-…
-- (bestehende ID-Strategie, auch für internationale Hochschulen).
-- =====================================================================

alter table public.universities
  add column market_access      text[] not null default '{}'
             check (market_access <@ array['physical_de', 'online_de']::text[]),
  add column online_de_status   text not null default 'not_assessed'
             check (online_de_status in ('confirmed', 'not_available', 'review', 'not_assessed')),
  add column online_de_basis    text,
  add column online_de_evidence jsonb not null default '{}',
  add column external_ids       jsonb not null default '{}',
  add column discovery          jsonb not null default '[]';

comment on column public.universities.market_access is
  'Was ProjectPathly Nutzern als verfügbar zeigen darf: physical_de (Präsenz in Deutschland bestätigt), online_de (online_de_status = confirmed). Leer = nicht verfügbar, auch bei Discovery-Kandidaten.';
comment on column public.universities.online_de_status is
  'confirmed: vollständiger Online-Abschluss und Zulassung aus Deutschland belegt; not_available: belegt nicht möglich; review: Kandidat aus ETER/IPEDS; not_assessed: deutsche Hochschule, Online-Angebote prüft ein späterer Scraper.';
comment on column public.universities.online_de_evidence is
  'Belege der Entscheidung: degree_evidence_url, eligibility_evidence_url, recognition_evidence_url, checked_at, note.';
comment on column public.universities.external_ids is
  'IDs in den Quelldatensätzen, z. B. {"eter": "ES0076", "ror": "…", "ipeds_unitid": "…", "opeid": "…"}.';
comment on column public.universities.discovery is
  'Warum die Hochschule aufgenommen wurde: Quelle, Satz-ID und Signale der internationalen Discovery (ETER/IPEDS).';
comment on column public.universities.listed_by is
  'Quellen, die die Hochschule nennen: Landesquellen (DE-NW, …) oder internationale Quellen-Namensräume (INTL-ETER, INTL-IPEDS). INTL-* sind keine Bundesländer.';

create index universities_market_access_idx on public.universities using gin (market_access);
create index universities_online_de_idx     on public.universities (online_de_status);
create index universities_country_idx       on public.universities (country);

alter table public.sources
  add column dataset_version text,
  add column record_id       text;

comment on column public.sources.dataset_version is
  'Fest gepinnte Version eines Datensatzes (z. B. ETER_fullDump_26032024); leer bei Landesquellen.';
comment on column public.sources.record_id is
  'Satz-ID in diesem Datensatz (ETER ID, IPEDS UNITID).';
