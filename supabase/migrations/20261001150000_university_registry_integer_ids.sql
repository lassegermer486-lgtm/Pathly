-- =====================================================================
-- Korrektur Hochschulregister:
--  - universities.id wird bigint (automatisch); die Scraper-ID
--    PTH-DE-XXXXXXXX wandert in die neue Spalte registry_id
--  - alle Verweise auf Hochschulen werden bigint
--  - locations.postal_code bleibt text, aber nur genau 5 Ziffern
--
-- Die Tabellen werden gelöscht und neu angelegt. Das ist nur zulässig,
-- solange sie leer sind – die Migration bricht sonst ab.
-- import_runs und set_updated_at() bleiben unverändert.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Sicherheitsprüfung: keine Daten vorhanden
-- ---------------------------------------------------------------------
do $$
begin
  if exists (select 1 from public.universities)
     or exists (select 1 from public.university_aliases)
     or exists (select 1 from public.locations)
     or exists (select 1 from public.sources)
     or exists (select 1 from public.university_flags) then
    raise exception 'Abbruch: Hochschultabellen enthalten bereits Daten. Diese Migration ist nur für leere Tabellen gedacht.';
  end if;
end;
$$;

-- ---------------------------------------------------------------------
-- Alte Tabellen entfernen (abhängige zuerst)
-- ---------------------------------------------------------------------
drop table public.university_flags;
drop table public.sources;
drop table public.locations;
drop table public.university_aliases;
drop table public.universities;

-- ---------------------------------------------------------------------
-- Hochschulen
-- ---------------------------------------------------------------------
create table public.universities (
  id                  bigint generated always as identity primary key,
  registry_id         text not null unique
                      check (registry_id ~ '^PTH-DE-[0-9A-F]{8}$'),
  name                text not null,
  name_variants       text[] not null default '{}',
  country             char(2) not null default 'DE',
  institution_type    text not null default 'unknown'
                      check (institution_type in (
                        'university', 'university_of_applied_sciences',
                        'art_music_university', 'university_of_education',
                        'public_administration', 'dual_university',
                        'theological_university', 'other', 'unknown')),
  ownership           text not null default 'unknown'
                      check (ownership in (
                        'public', 'private', 'church', 'federal', 'other', 'unknown')),
  recognition_status  text not null default 'unknown'
                      check (recognition_status in (
                        'state_recognized', 'public_by_law', 'other_recognized', 'unknown')),
  lifecycle_status    text not null default 'unknown'
                      check (lifecycle_status in (
                        'active', 'renamed', 'merged', 'closed', 'unknown')),
  official_url        text,
  listed_by           text[] not null default '{}',   -- Landesquellen, z. B. {DE-NW,DE-BB}
  is_listed           boolean not null default true,  -- false = im letzten Import nicht mehr gefunden
  last_seen_at        timestamptz,
  search              tsvector generated always as
                      (to_tsvector('german'::regconfig, name)) stored,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

comment on table public.universities is
  'Master-Registry: eine Zeile pro Hochschule, zusammengeführt aus allen Landesquellen.';
comment on column public.universities.id is
  'Interner Schlüssel für Verknüpfungen. Wird von der Datenbank vergeben.';
comment on column public.universities.registry_id is
  'Stabile ID aus dem Scraper (config/id_registry.json). Der Import erkennt Hochschulen über diese Spalte.';
comment on column public.universities.is_listed is
  'Wird beim Import auf false gesetzt, wenn keine Landesquelle die Hochschule mehr nennt. Zeilen werden nie gelöscht.';

create index universities_search_idx     on public.universities using gin (search);
create index universities_name_trgm_idx  on public.universities using gin (name extensions.gin_trgm_ops);
create index universities_type_idx       on public.universities (institution_type);
create index universities_ownership_idx  on public.universities (ownership);

create trigger universities_set_updated_at
  before update on public.universities
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------
-- Frühere Scraper-IDs (wenn zwei Hochschulen zusammengeführt wurden)
-- ---------------------------------------------------------------------
create table public.university_aliases (
  alias_registry_id  text primary key
                     check (alias_registry_id ~ '^PTH-DE-[0-9A-F]{8}$'),
  university_id      bigint not null references public.universities (id) on delete cascade
);

create index university_aliases_university_idx on public.university_aliases (university_id);

-- ---------------------------------------------------------------------
-- Standorte
-- ---------------------------------------------------------------------
create table public.locations (
  id             bigint generated always as identity primary key,
  university_id  bigint not null references public.universities (id) on delete cascade,
  name           text,                                   -- z. B. "Campus Garching"
  street         text,
  postal_code    text check (postal_code ~ '^[0-9]{5}$'),-- als Text: führende 0 (z. B. 01069 Dresden)
  city           text,
  state          text check (state ~ '^DE-[A-Z]{2}$'),   -- Bundesland des Standorts
  location_type  text not null default 'main'
                 check (location_type in ('main', 'branch', 'unknown')),
  latitude       double precision check (latitude  between -90  and 90),
  longitude      double precision check (longitude between -180 and 180),
  source_state   text,                                   -- welche Landesquelle ihn liefert
  source_url     text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index locations_university_idx on public.locations (university_id);
create index locations_state_idx      on public.locations (state);
create index locations_city_trgm_idx  on public.locations using gin (city extensions.gin_trgm_ops);

create trigger locations_set_updated_at
  before update on public.locations
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------
-- Herkunft der Daten
-- ---------------------------------------------------------------------
create table public.sources (
  id             bigint generated always as identity primary key,
  university_id  bigint not null references public.universities (id) on delete cascade,
  state          text,
  authority      text,          -- z. B. "Ministerium für Kultur und Wissenschaft NRW"
  url            text,
  category       text,
  source_type    text,          -- html, csv, pdf
  retrieved_at   timestamptz
);

create index sources_university_idx on public.sources (university_id);

-- ---------------------------------------------------------------------
-- Intern: Validierungs-Hinweise aus der Master-Registry
-- ---------------------------------------------------------------------
create table public.university_flags (
  id             bigint generated always as identity primary key,
  university_id  bigint not null references public.universities (id) on delete cascade,
  code           text not null,                 -- z. B. missing_website
  severity       text not null check (severity in ('high', 'medium', 'low')),
  detail         text
);

create index university_flags_university_idx on public.university_flags (university_id);

-- ---------------------------------------------------------------------
-- Zugriffsschutz (Row Level Security) – wie in der ersten Migration
-- ---------------------------------------------------------------------
alter table public.universities       enable row level security;
alter table public.university_aliases enable row level security;
alter table public.locations          enable row level security;
alter table public.sources            enable row level security;
alter table public.university_flags   enable row level security;

create policy "Hochschulen sind öffentlich lesbar"
  on public.universities for select to anon, authenticated using (true);

create policy "Alias-IDs sind öffentlich lesbar"
  on public.university_aliases for select to anon, authenticated using (true);

create policy "Standorte sind öffentlich lesbar"
  on public.locations for select to anon, authenticated using (true);

create policy "Quellen sind öffentlich lesbar"
  on public.sources for select to anon, authenticated using (true);

revoke all on public.university_flags from anon, authenticated;