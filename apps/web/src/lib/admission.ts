// Vergleicht ein Profil mit den Voraussetzungen eines Masters (Feature-Katalog D5).
// Reine Funktionen ohne Datenbank und ohne Browser: Das Profil verlässt nie das Gerät.
// Das Ergebnis ist eine Einschätzung, keine Zusage. Es entscheidet immer die Hochschule.

export type ProfileInput = {
  field: string;
  totalEcts: string;
  grade: string;
  areaEcts: Record<string, string>;
};

export const EMPTY_PROFILE: ProfileInput = { field: "", totalEcts: "", grade: "", areaEcts: {} };

export type Requirements = {
  degree: string;
  min_total_ects: number | null;
  min_grade: number | null;
  accepted_fields: string[];
  ects_requirements: { area: string; ects: number }[];
};

export type CheckStatus = "met" | "partial" | "unmet" | "unknown";

export type Check = {
  key: string;
  label: string;
  status: CheckStatus;
  detail: string;
};

export type Fit = "likely" | "partial" | "unlikely" | "incomplete" | "not_applicable";

export type Assessment = { fit: Fit; checks: Check[] };

// Annahmen für „teilweise“. Sie sind keine Regeln der Hochschulen und müssen mit echten
// Prüfungsordnungen überprüft werden.
export const TOTAL_ECTS_TOLERANCE = 30; // viele Hochschulen erlauben Auflagen in dieser Größe
export const GRADE_TOLERANCE = 0.3;
export const AREA_ECTS_SHARE = 0.5; // ab der Hälfte der verlangten ECTS gilt: nachholbar

function parseNumber(raw: string | undefined, min: number, max: number): number | null {
  if (!raw) return null;
  const value = Number(raw.trim().replace(",", "."));
  return Number.isFinite(value) && value >= min && value <= max ? value : null;
}

export const parseEcts = (raw: string | undefined) => parseNumber(raw, 0, 400);
export const parseGrade = (raw: string | undefined) => parseNumber(raw, 1, 4);

export function hasProfileData(profile: ProfileInput) {
  return Boolean(
    profile.field ||
      parseEcts(profile.totalEcts) !== null ||
      parseGrade(profile.grade) !== null ||
      Object.values(profile.areaEcts).some((v) => parseEcts(v) !== null),
  );
}

const grade1 = (value: number) => value.toLocaleString("de-DE", { minimumFractionDigits: 1 });

export function assess(
  program: Requirements,
  profile: ProfileInput,
  labels: { fields: Record<string, string>; areas: Record<string, string> },
): Assessment {
  if (program.degree !== "master") return { fit: "not_applicable", checks: [] };

  const checks: Check[] = [];

  if (program.min_total_ects !== null) {
    const need = program.min_total_ects;
    const have = parseEcts(profile.totalEcts);
    const label = `Mindestens ${need} ECTS im Bachelor`;
    if (have === null) {
      checks.push({ key: "total", label, status: "unknown", detail: "Trag deine ECTS ein." });
    } else if (have >= need) {
      checks.push({ key: "total", label, status: "met", detail: `Du hast ${have} ECTS.` });
    } else {
      const missing = need - have;
      checks.push({
        key: "total",
        label,
        status: missing <= TOTAL_ECTS_TOLERANCE ? "partial" : "unmet",
        detail:
          missing <= TOTAL_ECTS_TOLERANCE
            ? `Dir fehlen ${missing} ECTS. Oft lässt sich das über Auflagen nachholen, frag bei der Hochschule nach.`
            : `Dir fehlen ${missing} ECTS.`,
      });
    }
  }

  if (program.min_grade !== null) {
    const limit = Number(program.min_grade);
    const have = parseGrade(profile.grade);
    const label = `Note ${grade1(limit)} oder besser`;
    if (have === null) {
      checks.push({ key: "grade", label, status: "unknown", detail: "Trag deine Note ein." });
    } else if (have <= limit) {
      checks.push({ key: "grade", label, status: "met", detail: `Deine Note ist ${grade1(have)}.` });
    } else {
      const gap = Math.round((have - limit) * 10) / 10;
      checks.push({
        key: "grade",
        label,
        status: gap <= GRADE_TOLERANCE ? "partial" : "unmet",
        detail:
          gap <= GRADE_TOLERANCE
            ? `Deine Note ${grade1(have)} liegt knapp darüber. Praxis oder Tests können das manchmal ausgleichen.`
            : `Deine Note ${grade1(have)} liegt deutlich darüber.`,
      });
    }
  }

  if (program.accepted_fields.length > 0) {
    const names = program.accepted_fields.map((f) => labels.fields[f] ?? f).join(", ");
    const label = "Passendes Bachelorfach";
    if (!profile.field) {
      checks.push({ key: "field", label, status: "unknown", detail: `Vorgesehen sind: ${names}.` });
    } else if (program.accepted_fields.includes(profile.field)) {
      checks.push({ key: "field", label, status: "met", detail: `${labels.fields[profile.field] ?? profile.field} ist vorgesehen.` });
    } else {
      checks.push({
        key: "field",
        label,
        status: "partial",
        detail: `Vorgesehen sind: ${names}. Andere Fächer werden oft im Einzelfall geprüft.`,
      });
    }
  }

  for (const { area, ects: need } of program.ects_requirements) {
    const name = labels.areas[area] ?? area;
    const have = parseEcts(profile.areaEcts[area]);
    const label = `${need} ECTS in ${name}`;
    const key = `area-${area}`;
    if (have === null) {
      checks.push({ key, label, status: "unknown", detail: `Trag deine ECTS in ${name} ein.` });
    } else if (have >= need) {
      checks.push({ key, label, status: "met", detail: `Du hast ${have} ECTS.` });
    } else {
      const missing = need - have;
      const close = have >= need * AREA_ECTS_SHARE;
      checks.push({
        key,
        label,
        status: close ? "partial" : "unmet",
        detail: close
          ? `Dir fehlen ${missing} ECTS. Das lässt sich womöglich nachholen.`
          : `Dir fehlen ${missing} ECTS.`,
      });
    }
  }

  return { fit: overallFit(checks), checks };
}

function overallFit(checks: Check[]): Fit {
  if (checks.some((c) => c.status === "unmet")) return "unlikely";
  if (checks.some((c) => c.status === "partial")) return "partial";
  if (checks.some((c) => c.status === "unknown")) return "incomplete";
  return "likely";
}

// Reihenfolge in der Liste: das Passendste zuerst, Bachelor ohne Einschätzung dahinter
export const FIT_ORDER: Record<Fit, number> = {
  likely: 0,
  partial: 1,
  incomplete: 2,
  unlikely: 3,
  not_applicable: 4,
};
