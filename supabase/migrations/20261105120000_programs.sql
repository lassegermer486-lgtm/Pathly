-- =====================================================================
-- Studiengänge mit Zulassungsvoraussetzungen (Feature-Katalog C1, D4, D5)
--
-- Eine Zeile pro Studiengang. Die Voraussetzungen stehen bewusst in derselben
-- Tabelle, damit der Abgleich mit dem Profil im Browser ohne weitere Abfrage läuft.
-- is_demo markiert erfundene Einträge. Sie kommen nur über
-- supabase/seeds/dev-demo-programs.sql in die Dev-Datenbank, nie in die Live-Datenbank.
-- =====================================================================

create table public.programs (
  id                     bigint generated always as identity primary key,
  university_id          bigint not null references public.universities (id) on delete cascade,
  name                   text not null,
  degree                 text not null check (degree in ('bachelor', 'master')),
  degree_title           text not null,                 -- z. B. M.Sc.
  field                  text not null,                 -- Fachrichtung, Schlüssel aus lib/programs.ts
  study_models           text[] not null default '{}'
                         check (study_models <@ array['full_time', 'part_time', 'extra_occupational', 'dual']::text[]),
  languages              text[] not null default '{}',  -- z. B. {de,en}
  semesters              integer check (semesters > 0),
  ects                   integer check (ects > 0),
  start_terms            text[] not null default '{}'
                         check (start_terms <@ array['winter', 'summer']::text[]),
  tuition_per_semester_eur integer check (tuition_per_semester_eur >= 0), -- ohne Semesterbeitrag
  city                   text,
  program_url            text,

  -- Zulassung
  admission_type         text not null
                         check (admission_type in ('open', 'requirements', 'selection', 'nc')),
  min_total_ects         integer check (min_total_ects >= 0),
  min_grade              numeric(2, 1) check (min_grade between 1.0 and 4.0), -- schlechteste zugelassene Note
  accepted_fields        text[] not null default '{}',  -- leer = kein bestimmtes Bachelorfach verlangt
  ects_requirements      jsonb not null default '[]'    -- [{"area": "informatik", "ects": 60}]
                         check (jsonb_typeof(ects_requirements) = 'array'),
  tests                  text[] not null default '{}',  -- z. B. {GMAT,Eignungsgespräch}
  language_requirement   text,                          -- z. B. Englisch C1
  deadline_winter        text,                          -- z. B. 15.07.
  deadline_summer        text,
  notes                  text,

  -- Herkunft
  source_url             text,
  source_checked_at      date,
  is_demo                boolean not null default false,

  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now()
);

comment on table public.programs is
  'Studiengänge mit Zulassungsvoraussetzungen. is_demo = erfundene Daten für die Dev-Umgebung.';

create index programs_university_id_idx on public.programs (university_id);
create index programs_degree_field_idx on public.programs (degree, field);

create trigger programs_set_updated_at
  before update on public.programs
  for each row execute function public.set_updated_at();

alter table public.programs enable row level security;

create policy "Studiengänge sind öffentlich lesbar"
  on public.programs for select
  to anon, authenticated
  using (true);

revoke all on public.programs from anon, authenticated;
grant select on public.programs to anon, authenticated;
