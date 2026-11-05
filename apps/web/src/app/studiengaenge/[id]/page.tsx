import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalLinkIcon } from "lucide-react";
import { AdmissionPanel } from "@/components/admission-panel";
import { DemoNotice } from "@/components/demo-notice";
import { ProfileForm } from "@/components/profile-form";
import { Badge } from "@/components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getBachelorOptions } from "@/lib/bachelors";
import { showDemoFeatures } from "@/lib/flags";
import {
  ADMISSION_TYPES,
  LANGUAGES,
  PROGRAM_COLUMNS,
  STUDY_MODELS,
  TERMS,
  formatTuition,
  type Program,
} from "@/lib/programs";
import { createClient } from "@/lib/supabase/server";

async function getProgram(rawId: string) {
  if (!showDemoFeatures || !/^\d+$/.test(rawId)) return null;
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("programs")
    .select(PROGRAM_COLUMNS)
    .eq("id", Number(rawId))
    .maybeSingle();
  if (error) console.error("Studiengang konnte nicht geladen werden:", error);
  return data as unknown as Program | null;
}

export async function generateMetadata({ params }: PageProps<"/studiengaenge/[id]">): Promise<Metadata> {
  const p = await getProgram((await params).id);
  if (!p) return { title: "Studiengang nicht gefunden" };
  return { title: `${p.name} (${p.degree_title})`, robots: { index: false } };
}

export default async function ProgramPage({ params }: PageProps<"/studiengaenge/[id]">) {
  const p = await getProgram((await params).id);
  if (!p) notFound();

  const facts = [
    ["Dauer", p.semesters && `${p.semesters} Semester`],
    ["Umfang", p.ects && `${p.ects} ECTS`],
    ["Sprache", p.languages.map((l) => LANGUAGES[l] ?? l).join(", ")],
    ["Studienbeginn", p.start_terms.map((t) => TERMS[t] ?? t).join(", ")],
    ["Studienmodell", p.study_models.map((m) => STUDY_MODELS[m] ?? m).join(", ")],
    ["Kosten", formatTuition(p.tuition_per_semester_eur)],
  ].filter(([, value]) => value);

  const deadlines = [
    p.deadline_winter && `Wintersemester: bis ${p.deadline_winter}`,
    p.deadline_summer && `Sommersemester: bis ${p.deadline_summer}`,
  ].filter(Boolean);

  const further = [
    ...p.tests.map((test) => ["Zusätzlich verlangt", test]),
    ["Sprachnachweis", p.language_requirement],
    ["Bewerbungsfrist", deadlines.join(", ")],
    ["Hinweis", p.notes],
  ].filter(([, value]) => value);

  const isMaster = p.degree === "master";

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-12 sm:px-6">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink render={<Link href="/studiengaenge" />}>Studiengänge</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage className="line-clamp-1">{p.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <h1 className="mt-6 text-3xl font-bold tracking-tight text-balance sm:text-4xl">
        {p.name} ({p.degree_title})
      </h1>
      <p className="mt-2">
        {p.university.name}
        {p.city && ` · ${p.city}`}
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge variant="secondary">{ADMISSION_TYPES[p.admission_type]}</Badge>
      </div>
      {p.is_demo && <DemoNotice className="mt-6 max-w-3xl" />}
      {p.program_url && (
        <Button
          size="lg"
          className="mt-6 h-10 px-4"
          nativeButton={false}
          render={<a href={p.program_url} target="_blank" rel="noopener noreferrer" />}
        >
          Zur Studiengangsseite
          <ExternalLinkIcon data-icon="inline-end" />
        </Button>
      )}

      <div className="mt-10 grid items-start gap-8 lg:grid-cols-[1fr_20rem]">
        <div className="min-w-0">
          {facts.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {facts.map(([label, value]) => (
                <Card key={label as string} size="sm">
                  <CardHeader>
                    <CardDescription>{label}</CardDescription>
                    <CardTitle>{value}</CardTitle>
                  </CardHeader>
                </Card>
              ))}
            </div>
          )}

          {isMaster && (
            <section className="mt-12">
              <h2 className="text-xl font-semibold">Zulassung im Vergleich zu deinem Bachelor</h2>
              <AdmissionPanel
                requirements={p}
                selective={p.admission_type === "selection" || p.admission_type === "nc"}
              />
            </section>
          )}

          {further.length > 0 && (
            <section className="mt-12">
              <h2 className="text-xl font-semibold">Das solltest du außerdem wissen</h2>
              <dl className="mt-4 space-y-3">
                {further.map(([label, value], index) => (
                  <div key={index}>
                    <dt className="text-sm font-medium">{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}

          {p.source_url && (
            <section className="mt-12">
              <h2 className="text-xl font-semibold">Quelle</h2>
              <a
                href={p.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block break-all underline underline-offset-4"
              >
                {p.source_url}
              </a>
              {p.source_checked_at && (
                <p className="mt-1 text-sm">
                  Geprüft am {new Date(p.source_checked_at).toLocaleDateString("de-DE")}
                </p>
              )}
            </section>
          )}
        </div>
        {isMaster && <ProfileForm bachelors={await getBachelorOptions()} className="lg:sticky lg:top-24" />}
      </div>
    </main>
  );
}
