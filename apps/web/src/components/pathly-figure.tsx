import { cn } from "@/lib/utils";

const WIDTH = 177;
const HEIGHT = 346;
export const PATHLY_FIGURE_RATIO = WIDTH / HEIGHT;
// Waagerechte Stelle der greifenden Hand, gemessen an der Breite. Dort steht ein Mast oder Griff.
export const PATHLY_FIGURE_GRIP_X = (187 - 22) / WIDTH;

const COLORS = {
  forest: "#053438",
  darkest: "#033527",
  dark: "#044b39",
  mid: "#0a6a50",
  soft: "#16976f",
  emerald: "#1ea97b",
  lime: "#cbf39d",
  green: "#72c613",
  skin: "#f0d5bc",
  skinShade: "#dcb99a",
  hair: "#4a4f52",
  hairLight: "#6b7073",
};

// Jede Fläche: Farbe und Eckpunkte. Die Figur besteht nur aus Dreiecken und Vielecken.
const FACETS: [keyof typeof COLORS | "white", string][] = [
  // Beine und Schuhe
  ["darkest", "76,296 96,298 94,338 78,338"],
  ["dark", "104,298 126,296 124,338 108,338"],
  ["forest", "74,336 95,336 96,348 60,348"],
  ["forest", "107,336 129,336 142,348 107,348"],

  // Linker Arm hinter dem Talar, Hand in der Hüfte
  ["dark", "62,172 38,192 46,238 64,222"],
  ["mid", "46,238 64,222 86,250 74,264"],
  ["skinShade", "74,264 86,250 96,258 88,272"],

  // Talar
  ["mid", "62,170 100,178 96,300 46,296"],
  ["emerald", "100,178 140,170 158,296 96,300"],
  ["dark", "62,170 84,240 46,296"],
  ["soft", "140,170 122,240 158,296"],
  ["soft", "100,178 122,240 96,300 84,240"],
  ["mid", "84,240 96,300 66,298"],

  // Arm, der den Mast greift
  ["soft", "136,172 150,194 182,208 180,186"],
  ["emerald", "136,172 180,186 158,180"],

  // Hals und Kragen
  ["skinShade", "90,146 112,148 110,166 92,164"],
  ["lime", "82,160 100,180 118,160 126,170 100,208 74,170"],
  ["green", "100,180 118,160 126,170 100,208"],

  // Kopf
  ["skin", "66,62 136,62 142,100 132,134 108,150 88,146 70,124"],
  ["skinShade", "66,62 88,62 90,146 88,146 70,124"],
  ["skinShade", "62,96 70,92 72,114 64,110"],
  ["skinShade", "106,92 120,120 102,122"],
  ["hair", "60,58 74,58 72,106 58,92"],
  ["hairLight", "74,58 90,58 76,84 72,106"],
  ["hair", "134,58 142,58 144,88 138,82"],

  // Gesicht
  ["white", "90,92 104,91 103,101 91,102"],
  ["white", "118,91 132,92 131,101 119,101"],
  ["forest", "96,92 103,92 103,101 96,101"],
  ["forest", "123,92 130,92 130,101 123,101"],
  ["hair", "87,84 106,80 106,86 88,90"],
  ["hair", "116,80 135,84 134,90 116,86"],
  ["mid", "96,128 124,125 116,138 103,139"],
  ["white", "100,129 120,127 115,132 103,133"],

  // Absolventenhut mit Quaste
  ["darkest", "62,44 140,44 134,72 100,80 68,70"],
  ["forest", "100,62 140,44 134,72 100,80"],
  ["darkest", "28,36 100,10 100,62"],
  ["dark", "100,10 174,38 100,62"],
  ["mid", "100,10 174,38 138,28"],
  ["green", "98,34 104,34 104,38 40,42 40,40"],
  ["green", "37,40 41,40 41,74 37,74"],
  ["lime", "32,74 46,74 48,94 30,94"],
  ["green", "39,74 46,74 48,94 39,94"],

  // Hand um den Mast
  ["skin", "176,184 196,185 197,207 178,209"],
  ["skinShade", "176,196 197,196 197,207 178,209"],
];

// Die Pathly-Figur mit Absolventenhut, eine eigene Vektorgrafik im Low-Poly-Stil.
// Größe über die Klasse setzen, z. B. <PathlyFigure className="h-40" />.
// Mit `title` wird sie für Screenreader benannt, ohne gilt sie als Dekoration.
export function PathlyFigure({ title, className }: { title?: string; className?: string }) {
  return (
    <svg
      viewBox={`22 6 ${WIDTH} ${HEIGHT}`}
      className={cn("w-auto", className)}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {FACETS.map(([color, points], index) => (
        <polygon key={index} points={points} fill={color === "white" ? "#ffffff" : COLORS[color]} />
      ))}
    </svg>
  );
}
