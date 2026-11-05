import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { TriangleAlertIcon } from "lucide-react";
import { DemoNotice } from "@/components/demo-notice";
import { FilterMenu } from "@/components/filter-menu";
import { ProfileForm } from "@/components/profile-form";
import { ProgramList } from "@/components/program-list";
import { SearchForm } from "@/components/search-form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { getBachelorOptions } from "@/lib/bachelors";
import { showDemoFeatures } from "@/lib/flags";
import {
  ADMISSION_TYPES,
  DEGREES,
  FIELDS,
  PROGRAM_COLUMNS,
  STUDY_MODELS,
  type Program,
} from "@/lib/programs";
import { likePattern, list, param } from "@/lib/search-params";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Studiengänge und Zulassung",
  robots: { index: false },
};

const FILTERS = [
  { name: "abschluss", label: "Abschluss", all: "Alle Abschlüsse", options: DEGREES },
  { name: "fach", label: "Fachrichtung", all: "Alle Fachrichtungen", options: FIELDS },
  { name: "modell", label: "Studienmodell", all: "Alle Modelle", options: STUDY_MODELS },
  { name: "zulassung", label: "Zulassung", all: "Alle Zulassungen", options: ADMISSION_TYPES },
] as const;

export default async function ProgramsPage({ searchParams }: PageProps<"/studiengaenge">) {
  if (!showDemoFeatures) notFound();

  const sp = await searchParams;
  const q = param(sp.q).slice(0, 100);
  const values = {
    abschluss: list(sp.abschluss, DEGREES),
    fach: list(sp.fach, FIELDS),
    modell: list(sp.modell, STUDY_MODELS),
    zulassung: list(sp.zulassung, ADMISSION_TYPES),
  };
  const hasFilter = Boolean(q || Object.values(values).some((v) => v.length));

  const supabase = await createClient();
  let query = supabase.from("programs").select(PROGRAM_COLUMNS).order("name").limit(200);
  if (q) query = query.ilike("name", likePattern(q));
  if (values.abschluss.length) query = query.in("degree", values.abschluss);
  if (values.fach.length) query = query.in("field", values.fach);
  if (values.modell.length) query = query.overlaps("study_models", values.modell);
  if (values.zulassung.length) query = query.in("admission_type", values.zulassung);

  const { data, error } = await query;
  if (error) console.error("Studiengänge konnten nicht geladen werden:", error);
  const programs = (data ?? []) as unknown as Program[];
  const bachelors = await getBachelorOptions();

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-12 sm:px-6">
      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">Studiengänge und Zulassung</h1>
      <p className="mt-3 max-w-2xl">
        Finde Studiengänge und sieh direkt, welche Voraussetzungen du schon erfüllst und was dir
        noch fehlt.
      </p>
      <DemoNotice className="mt-6 max-w-3xl" />

      <SearchForm
        action="/studiengaenge"
        defaultValue={q}
        placeholder="z. B. Informatik, Data Science …"
        label="Studiengang suchen"
        className="mt-8 max-w-3xl"
      >
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4 sm:gap-3">
          {FILTERS.map((f) => (
            <FilterMenu
              key={f.name}
              name={f.name}
              label={f.label}
              allLabel={f.all}
              options={f.options}
              value={values[f.name]}
            />
          ))}
        </div>
      </SearchForm>

      {hasFilter && (
        <Button variant="ghost" size="sm" className="mt-3" nativeButton={false} render={<Link href="/studiengaenge" />}>
          Filter zurücksetzen
        </Button>
      )}

      <div className="mt-10 grid items-start gap-8 lg:grid-cols-[20rem_1fr]">
        <ProfileForm bachelors={bachelors} className="lg:sticky lg:top-24" />
        {error ? (
          <Alert variant="destructive">
            <TriangleAlertIcon />
            <AlertTitle>Studiengänge konnten nicht geladen werden</AlertTitle>
            <AlertDescription>Versuch es gleich noch einmal.</AlertDescription>
          </Alert>
        ) : (
          <ProgramList programs={programs} />
        )}
      </div>
    </main>
  );
}
