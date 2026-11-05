"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { MapPinIcon, SearchXIcon } from "lucide-react";
import { FitBadge } from "@/components/fit-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { assess, FIT_ORDER, hasProfileData } from "@/lib/admission";
import { ADMISSION_TYPES, AREAS, FIELDS, STUDY_MODELS, type Program } from "@/lib/programs";
import { useProfile } from "@/lib/use-profile";

export function ProgramList({ programs }: { programs: Program[] }) {
  const [profile] = useProfile();
  const [hideUnlikely, setHideUnlikely] = useState(false);
  const active = hasProfileData(profile);

  const rows = useMemo(() => {
    const assessed = programs.map((program) => ({
      program,
      ...assess(program, profile, { fields: FIELDS, areas: AREAS }),
    }));
    // Ohne Angaben bleibt die Reihenfolge nach Namen, sonst das Passendste zuerst
    return active ? assessed.sort((a, b) => FIT_ORDER[a.fit] - FIT_ORDER[b.fit]) : assessed;
  }, [programs, profile, active]);

  const unlikelyCount = rows.filter((r) => r.fit === "unlikely").length;
  const visible = active && hideUnlikely ? rows.filter((r) => r.fit !== "unlikely") : rows;

  return (
    <div className="min-w-0">
      <div className="flex min-h-9 flex-wrap items-center justify-between gap-2">
        <p className="text-sm" aria-live="polite">
          {visible.length} {visible.length === 1 ? "Studiengang" : "Studiengänge"}
        </p>
        {active && unlikelyCount > 0 && (
          <Button variant="ghost" size="sm" onClick={() => setHideUnlikely(!hideUnlikely)}>
            {hideUnlikely ? "Alle anzeigen" : `${unlikelyCount} eher unpassende ausblenden`}
          </Button>
        )}
      </div>

      {visible.length === 0 ? (
        <Empty className="mt-4 border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <SearchXIcon />
            </EmptyMedia>
            <EmptyTitle>Kein Studiengang gefunden</EmptyTitle>
            <EmptyDescription>Probier einen kürzeren Suchbegriff oder entferne Filter.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <ul className="mt-4 grid gap-4 md:grid-cols-2">
          {visible.map(({ program: p, fit, checks }) => {
            const gaps = checks.filter((c) => c.status === "partial" || c.status === "unmet");
            return (
              <li key={p.id} className="min-w-0">
                <Card className="relative h-full transition-colors hover:bg-accent/60 hover:ring-accent-foreground/40">
                  <CardHeader>
                    <CardTitle className="leading-snug">
                      <Link href={`/studiengaenge/${p.id}`} className="after:absolute after:inset-0">
                        {p.name} ({p.degree_title})
                      </Link>
                    </CardTitle>
                    <CardDescription className="text-foreground">{p.university.name}</CardDescription>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {active && <FitBadge fit={fit} />}
                      <Badge variant="secondary">{ADMISSION_TYPES[p.admission_type]}</Badge>
                      {p.study_models.map((m) => (
                        <Badge key={m} variant="outline">
                          {STUDY_MODELS[m] ?? m}
                        </Badge>
                      ))}
                    </div>
                    {active && gaps.length > 0 && (
                      <ul className="mt-2 list-disc space-y-1 pl-4 text-sm">
                        {gaps.slice(0, 2).map((c) => (
                          <li key={c.key}>{c.label}</li>
                        ))}
                        {gaps.length > 2 && <li>und {gaps.length - 2} weitere</li>}
                      </ul>
                    )}
                  </CardHeader>
                  <CardFooter className="mt-auto flex-wrap gap-x-4 gap-y-1 text-sm">
                    {p.city && (
                      <span className="inline-flex items-center gap-1">
                        <MapPinIcon className="size-3.5" />
                        {p.city}
                      </span>
                    )}
                    {p.semesters && <span>{p.semesters} Semester</span>}
                    {p.ects && <span>{p.ects} ECTS</span>}
                  </CardFooter>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
