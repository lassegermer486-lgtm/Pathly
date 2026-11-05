// Bezeichnungen und Typen für Studiengänge (siehe supabase/migrations/…_programs.sql)

export const DEGREES: Record<string, string> = {
  bachelor: "Bachelor",
  master: "Master",
};

export const FIELDS: Record<string, string> = {
  informatik: "Informatik",
  wirtschaftsinformatik: "Wirtschaftsinformatik",
  wirtschaft: "Wirtschaft",
  ingenieurwesen: "Ingenieurwesen",
  naturwissenschaften: "Naturwissenschaften",
};

// Fachgebiete, in denen Master bestimmte ECTS verlangen
export const AREAS: Record<string, string> = {
  informatik: "Informatik",
  mathematik: "Mathematik",
  wirtschaft: "Wirtschaft",
  technik: "Technik",
};

export const STUDY_MODELS: Record<string, string> = {
  full_time: "Vollzeit",
  part_time: "Teilzeit",
  extra_occupational: "Berufsbegleitend",
  dual: "Dual",
};

export const ADMISSION_TYPES: Record<string, string> = {
  open: "Zulassungsfrei",
  requirements: "Mit Voraussetzungen",
  selection: "Auswahlverfahren",
  nc: "Numerus clausus",
};

export const LANGUAGES: Record<string, string> = {
  de: "Deutsch",
  en: "Englisch",
};

export const TERMS: Record<string, string> = {
  winter: "Wintersemester",
  summer: "Sommersemester",
};

export type EctsRequirement = { area: string; ects: number };

export type Program = {
  id: number;
  name: string;
  degree: string;
  degree_title: string;
  field: string;
  study_models: string[];
  languages: string[];
  semesters: number | null;
  ects: number | null;
  start_terms: string[];
  tuition_per_semester_eur: number | null;
  city: string | null;
  program_url: string | null;
  admission_type: string;
  min_total_ects: number | null;
  min_grade: number | null;
  accepted_fields: string[];
  ects_requirements: EctsRequirement[];
  tests: string[];
  language_requirement: string | null;
  deadline_winter: string | null;
  deadline_summer: string | null;
  notes: string | null;
  source_url: string | null;
  source_checked_at: string | null;
  is_demo: boolean;
  university: { id: number; name: string };
};

export const PROGRAM_COLUMNS =
  "id, name, degree, degree_title, field, study_models, languages, semesters, ects, start_terms, " +
  "tuition_per_semester_eur, city, program_url, admission_type, min_total_ects, min_grade, " +
  "accepted_fields, ects_requirements, tests, language_requirement, deadline_winter, deadline_summer, " +
  "notes, source_url, source_checked_at, is_demo, university:universities!inner(id, name)";

export function formatTuition(eur: number | null) {
  if (eur === null) return null;
  if (eur === 0) return "Keine Studiengebühren";
  return `${eur.toLocaleString("de-DE")} € pro Semester`;
}
