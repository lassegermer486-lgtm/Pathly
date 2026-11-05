// Mehrfachauswahl: "a,b" bzw. ?x=a&x=b → nur gültige Schlüssel, ohne Duplikate
export function list(value: string | string[] | undefined, allowed: Record<string, string>) {
  const raw = (Array.isArray(value) ? value : [value ?? ""]).flatMap((v) => v.split(","));
  return [...new Set(raw.map((v) => v.trim()).filter((v) => v in allowed))];
}

export function param(value: string | string[] | undefined) {
  return typeof value === "string" ? value.trim() : "";
}

// Macht einen Suchbegriff für ilike sicher
export function likePattern(q: string) {
  return `%${q.replace(/[%_\\]/g, "\\$&")}%`;
}
