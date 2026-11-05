// Funktionen mit Demodaten erscheinen nur lokal und auf dem Dev-Server, nie auf pathly.info.
// Standard ist „aus“: Fehlt die Angabe von Vercel, bleibt die Funktion verborgen.
export const showDemoFeatures =
  process.env.NODE_ENV === "development" ||
  process.env.NEXT_PUBLIC_VERCEL_ENV === "preview";
