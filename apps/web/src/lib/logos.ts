import { showDemoFeatures } from "@/lib/flags";

// Logos sind geschützt: Live erscheinen sie erst mit schriftlicher Freigabe der Hochschule.
// Bis dahin nur zur Vorschau auf dem Dev-Server. Datei ohne Freigabe nicht nach main übernehmen.
const LOGO_PREVIEWS: Record<string, { src: string; width: number; height: number }> = {
  "PTH-DE-138698E2": { src: "/logos/PTH-DE-138698E2.png", width: 454, height: 116 }, // Hochschule Reutlingen
};

export function universityLogo(registryId: string) {
  return showDemoFeatures ? (LOGO_PREVIEWS[registryId] ?? null) : null;
}
