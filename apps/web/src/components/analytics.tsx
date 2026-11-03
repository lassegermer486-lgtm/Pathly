"use client";

import { Analytics as VercelAnalytics, type BeforeSendEvent } from "@vercel/analytics/next";

// Nur Such- und Filterparameter dürfen in die Statistik – alles andere
// (z. B. Weiterleitungs- oder Fehlerparameter beim Login) wird entfernt.
const ALLOWED_PARAMS = new Set(["q", "typ", "traeger", "land", "seite"]);

function stripUrl(event: BeforeSendEvent): BeforeSendEvent {
  const url = new URL(event.url);
  for (const key of [...url.searchParams.keys()]) {
    if (!ALLOWED_PARAMS.has(key)) url.searchParams.delete(key);
  }
  url.hash = "";
  return { ...event, url: url.toString() };
}

export function Analytics() {
  return <VercelAnalytics beforeSend={stripUrl} />;
}
