import { showDemoFeatures } from "@/lib/flags";

// Prototyp: Hochschulen mit Campus-Datei unter public/campus/<registry_id>.geojson
const CAMPUS_MAPS = new Set(["PTH-DE-138698E2"]); // Hochschule Reutlingen

export function campusDataUrl(registryId: string) {
  return showDemoFeatures && CAMPUS_MAPS.has(registryId) ? `/campus/${registryId}.geojson` : null;
}
