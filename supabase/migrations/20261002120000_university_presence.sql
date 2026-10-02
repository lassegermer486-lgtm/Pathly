-- =====================================================================
-- Hochschulregister v1.3: physische Präsenz in Deutschland
--
-- Nur neue Spalten, nichts wird gelöscht oder umbenannt. Bestehende
-- Zeilen gelten bis zum nächsten Import als "zu prüfen".
-- Erst diese Migration einspielen, dann den v1.3-Import ausführen.
-- =====================================================================

alter table public.universities
  add column german_physical_presence boolean,
  add column presence_status text not null default 'review'
             check (presence_status in ('confirmed', 'not_present', 'review')),
  add column presence_basis  text;

comment on column public.universities.german_physical_presence is
  'true: mindestens ein aktiver Standort in Deutschland; false: alle deutschen Standorte geschlossen/verlegt (geprüft); null: unklar.';
comment on column public.universities.presence_status is
  'confirmed / not_present / review – abgeleitet aus locations.location_status und den Landes-Listungen.';
comment on column public.universities.presence_basis is
  'Herkunft der Aussage: state_source_and_verified_website (Standort mit Ort), state_listing_without_city_and_verified_website (nur Landes-Listung), manual_review, uncertain_locations. Vorläufig; Scraper 2 kann mit Standortdaten bestätigen oder korrigieren.';

create index universities_presence_idx on public.universities (presence_status);

alter table public.locations
  add column country                      char(2) not null default 'DE',
  add column location_status              text not null default 'uncertain'
                                          check (location_status in ('active', 'closed', 'moved', 'uncertain')),
  add column location_status_basis        text,
  add column location_status_evidence_url text;

comment on column public.locations.location_status is
  'active: aktuell gelistet und Website verifiziert; closed/moved: nur nach Prüfung mit Beleg; uncertain: Belege reichen nicht.';
comment on column public.locations.location_status_basis is
  'Warum dieser Status: state_source_and_verified_website, manual_review oder insufficient_evidence: ...';
