"use client";

import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { applyCurriculum, EMPTY_PROFILE, hasProfileData, parseEcts, parseGrade } from "@/lib/admission";
import { AREAS, FIELDS, type BachelorOption } from "@/lib/programs";
import { useProfile } from "@/lib/use-profile";
import { cn } from "@/lib/utils";

const SELECT_CLASS = "w-full *:data-[slot=native-select]:max-md:h-10";

function NumberField({
  id,
  label,
  value,
  placeholder,
  invalid,
  error,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  placeholder?: string;
  invalid: boolean;
  error: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        inputMode="decimal"
        autoComplete="off"
        value={value}
        placeholder={placeholder}
        aria-invalid={invalid}
        aria-describedby={invalid ? `${id}-fehler` : undefined}
        onChange={(e) => onChange(e.target.value)}
      />
      {invalid && (
        <p id={`${id}-fehler`} className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

export function ProfileForm({ bachelors, className }: { bachelors: BachelorOption[]; className?: string }) {
  const [profile, setProfile] = useProfile();
  const set = (patch: Partial<typeof profile>) => setProfile({ ...profile, ...patch });

  const universities = useMemo(() => {
    const byId = new Map(bachelors.map((b) => [String(b.university.id), b.university.name]));
    return [...byId].sort(([, a], [, b]) => a.localeCompare(b, "de"));
  }, [bachelors]);

  // Eine gespeicherte Auswahl kann veraltet sein, wenn sich die Daten geändert haben
  const universityId = universities.some(([id]) => id === profile.bachelorUniversityId)
    ? profile.bachelorUniversityId
    : "";
  const options = bachelors.filter((b) => String(b.university.id) === universityId);
  const selected = options.find((b) => String(b.id) === profile.bachelorProgramId);
  const hasManualData = !selected && hasProfileData({ ...profile, grade: "" });

  function selectUniversity(id: string) {
    // Neue Hochschule: Die Werte des alten Studiengangs gelten nicht mehr
    setProfile({
      ...(selected ? { ...EMPTY_PROFILE, grade: profile.grade } : profile),
      bachelorUniversityId: id,
      bachelorProgramId: "",
    });
  }

  function selectProgram(id: string) {
    const bachelor = options.find((b) => String(b.id) === id);
    if (bachelor) setProfile(applyCurriculum(profile, bachelor));
    else setProfile({ ...EMPTY_PROFILE, grade: profile.grade, bachelorUniversityId: universityId });
  }

  const gradeInvalid = Boolean(profile.grade) && parseGrade(profile.grade) === null;

  return (
    <Card className={cn("rounded-2xl", className)}>
      <CardHeader>
        <CardTitle>Dein Bachelor</CardTitle>
        <CardDescription>
          Sag uns, wo du studiert hast. Den Rest ergänzen wir aus dem Studienplan. Deine Angaben
          bleiben auf deinem Gerät.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="profil-hochschule">Hochschule</Label>
          <NativeSelect
            id="profil-hochschule"
            className={SELECT_CLASS}
            value={universityId}
            onChange={(e) => selectUniversity(e.target.value)}
          >
            <NativeSelectOption value="">Bitte wählen</NativeSelectOption>
            {universities.map(([id, name]) => (
              <NativeSelectOption key={id} value={id}>
                {name}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>

        {universityId && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="profil-studiengang">Bachelor-Studiengang</Label>
            <NativeSelect
              id="profil-studiengang"
              className={SELECT_CLASS}
              value={selected ? String(selected.id) : ""}
              onChange={(e) => selectProgram(e.target.value)}
            >
              <NativeSelectOption value="">Bitte wählen</NativeSelectOption>
              {options.map((b) => (
                <NativeSelectOption key={b.id} value={b.id}>
                  {b.name} ({b.degree_title})
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
        )}

        {selected && (
          <div className="rounded-lg bg-brand-mint/40 p-3 text-sm" role="status">
            <p className="font-medium">Aus dem Studienplan übernommen</p>
            <p className="mt-1">
              {[
                profile.totalEcts && `${profile.totalEcts} ECTS`,
                ...Object.entries(AREAS)
                  .filter(([key]) => profile.areaEcts[key] && profile.areaEcts[key] !== "0")
                  .map(([key, label]) => `${label} ${profile.areaEcts[key]}`),
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
            <p className="mt-1 text-muted-foreground">
              Deine Vertiefung kann abweichen. Unten kannst du alles anpassen.
            </p>
          </div>
        )}

        <NumberField
          id="profil-note"
          label="Note (optional)"
          value={profile.grade}
          placeholder="z. B. 2,3"
          invalid={gradeInvalid}
          error="Trag eine Note von 1,0 bis 4,0 ein."
          onChange={(grade) => set({ grade })}
        />

        <details className="group" open={hasManualData || undefined}>
          <summary className="cursor-pointer py-2 text-sm font-medium underline-offset-4 hover:underline">
            {selected ? "Werte anpassen" : "Nicht dabei? Selbst eintragen"}
          </summary>
          <div className="mt-2 flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="profil-fach">Fachrichtung</Label>
              <NativeSelect
                id="profil-fach"
                className={SELECT_CLASS}
                value={profile.field}
                onChange={(e) => set({ field: e.target.value })}
              >
                <NativeSelectOption value="">Bitte wählen</NativeSelectOption>
                {Object.entries(FIELDS).map(([key, label]) => (
                  <NativeSelectOption key={key} value={key}>
                    {label}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
            <NumberField
              id="profil-ects"
              label="ECTS gesamt"
              value={profile.totalEcts}
              placeholder="z. B. 180"
              invalid={Boolean(profile.totalEcts) && parseEcts(profile.totalEcts) === null}
              error="Trag eine Zahl von 0 bis 400 ein."
              onChange={(totalEcts) => set({ totalEcts })}
            />
            <fieldset>
              <legend className="text-sm font-medium">ECTS nach Fachgebiet</legend>
              <div className="mt-2 grid grid-cols-2 items-start gap-3">
                {Object.entries(AREAS).map(([key, label]) => {
                  const value = profile.areaEcts[key] ?? "";
                  return (
                    <NumberField
                      key={key}
                      id={`profil-${key}`}
                      label={label}
                      value={value}
                      invalid={Boolean(value) && parseEcts(value) === null}
                      error="Trag eine Zahl von 0 bis 400 ein."
                      onChange={(next) => set({ areaEcts: { ...profile.areaEcts, [key]: next } })}
                    />
                  );
                })}
              </div>
            </fieldset>
          </div>
        </details>

        {(hasProfileData(profile) || universityId) && (
          <Button variant="ghost" size="sm" className="self-start" onClick={() => setProfile(EMPTY_PROFILE)}>
            Angaben löschen
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
