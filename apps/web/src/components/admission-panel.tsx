"use client";

import { FitBadge, STATUS_COLORS, STATUS_ICONS } from "@/components/fit-badge";
import { Item, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item";
import { assess, hasProfileData, type Requirements } from "@/lib/admission";
import { AREAS, FIELDS } from "@/lib/programs";
import { useProfile } from "@/lib/use-profile";

const STATUS_TEXT = {
  met: "Erfüllt",
  partial: "Teilweise erfüllt",
  unmet: "Eher nicht erfüllt",
  unknown: "Angabe fehlt",
};

export function AdmissionPanel({ requirements, selective }: { requirements: Requirements; selective: boolean }) {
  const [profile] = useProfile();
  const { fit, checks } = assess(requirements, profile, { fields: FIELDS, areas: AREAS });
  const active = hasProfileData(profile);

  if (checks.length === 0) {
    return <p className="mt-3">Für diesen Studiengang gibt es keine Mindestwerte zum Vergleichen.</p>;
  }

  return (
    <div className="mt-3">
      <div aria-live="polite">{active && <FitBadge fit={fit} />}</div>
      <ItemGroup className="mt-4 gap-3">
        {checks.map((c) => {
          const Icon = STATUS_ICONS[c.status];
          return (
            <Item key={c.key} variant="outline" className="items-start">
              <ItemMedia variant="icon">
                <Icon className={STATUS_COLORS[c.status]} aria-hidden />
              </ItemMedia>
              <ItemContent>
                <ItemTitle>{c.label}</ItemTitle>
                <ItemDescription className="line-clamp-none text-foreground">
                  <span className="sr-only">{STATUS_TEXT[c.status]}: </span>
                  {c.detail}
                </ItemDescription>
              </ItemContent>
            </Item>
          );
        })}
      </ItemGroup>
      <p className="mt-4 text-sm">
        Das ist eine Einschätzung auf Basis deiner Angaben, keine Zusage.
        {selective && " Auch wer alles erfüllt, durchläuft hier noch ein Auswahlverfahren."} Es
        entscheidet immer die Hochschule, jedes Profil ist anders.
      </p>
    </div>
  );
}
