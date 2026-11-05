-- ECTS pro Fachgebiet laut Studienplan, z. B. {"informatik": 60, "wirtschaft": 60}.
-- Damit genügen Hochschule und Bachelor-Studiengang, um das Profil vorzubefüllen.
alter table public.programs
  add column curriculum_ects jsonb not null default '{}'
  check (jsonb_typeof(curriculum_ects) = 'object');

comment on column public.programs.curriculum_ects is
  'ECTS pro Fachgebiet laut Studienplan. Vertiefungen können abweichen, das Profil bleibt änderbar.';
