// Öffentlich sichtbar sind nur Hochschulen mit bestätigtem Zugang in
// Deutschland (siehe universities.market_access in den Migrationen).
export const PUBLIC_MARKET_ACCESS = ["physical_de", "online_de"];

export const INSTITUTION_TYPES: Record<string, string> = {
  university: "Universität",
  university_of_applied_sciences: "Hochschule für angewandte Wissenschaften",
  art_music_university: "Kunst- und Musikhochschule",
  university_of_education: "Pädagogische Hochschule",
  public_administration: "Verwaltungshochschule",
  dual_university: "Duale Hochschule",
  theological_university: "Theologische Hochschule",
  other: "Sonstige Hochschule",
};

export const OWNERSHIPS: Record<string, string> = {
  public: "staatlich",
  private: "privat",
  church: "kirchlich",
  federal: "Bund",
  other: "sonstige Trägerschaft",
};

export const STATES: Record<string, string> = {
  "DE-BW": "Baden-Württemberg",
  "DE-BY": "Bayern",
  "DE-BE": "Berlin",
  "DE-BB": "Brandenburg",
  "DE-HB": "Bremen",
  "DE-HH": "Hamburg",
  "DE-HE": "Hessen",
  "DE-MV": "Mecklenburg-Vorpommern",
  "DE-NI": "Niedersachsen",
  "DE-NW": "Nordrhein-Westfalen",
  "DE-RP": "Rheinland-Pfalz",
  "DE-SL": "Saarland",
  "DE-SN": "Sachsen",
  "DE-ST": "Sachsen-Anhalt",
  "DE-SH": "Schleswig-Holstein",
  "DE-TH": "Thüringen",
};

export function hostname(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
