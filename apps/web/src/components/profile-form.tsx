"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { EMPTY_PROFILE, hasProfileData, parseEcts, parseGrade } from "@/lib/admission";
import { AREAS, FIELDS } from "@/lib/programs";
import { useProfile } from "@/lib/use-profile";
import { cn } from "@/lib/utils";

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

export function ProfileForm({ className }: { className?: string }) {
  const [profile, setProfile] = useProfile();
  const set = (patch: Partial<typeof profile>) => setProfile({ ...profile, ...patch });

  return (
    <Card className={cn("rounded-2xl", className)}>
      <CardHeader>
        <CardTitle>Dein Bachelor</CardTitle>
        <CardDescription>
          Wir vergleichen deine Angaben mit den Voraussetzungen der Master. Sie bleiben
          auf deinem Gerät.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="profil-fach">Fachrichtung</Label>
          <NativeSelect
            id="profil-fach"
            className="w-full *:data-[slot=native-select]:max-md:h-10"
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
        <div className="grid grid-cols-2 items-start gap-3">
          <NumberField
            id="profil-ects"
            label="ECTS gesamt"
            value={profile.totalEcts}
            placeholder="z. B. 180"
            invalid={Boolean(profile.totalEcts) && parseEcts(profile.totalEcts) === null}
            error="Trag eine Zahl von 0 bis 400 ein."
            onChange={(totalEcts) => set({ totalEcts })}
          />
          <NumberField
            id="profil-note"
            label="Note"
            value={profile.grade}
            placeholder="z. B. 2,3"
            invalid={Boolean(profile.grade) && parseGrade(profile.grade) === null}
            error="Trag eine Note von 1,0 bis 4,0 ein."
            onChange={(grade) => set({ grade })}
          />
        </div>
        <fieldset className="flex flex-col gap-3">
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
        {hasProfileData(profile) && (
          <Button variant="ghost" size="sm" className="self-start" onClick={() => setProfile(EMPTY_PROFILE)}>
            Angaben löschen
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
