// Der Worker der Kartenbibliothek muss als eigene Datei erreichbar sein, das Bundling
// von Next findet ihn nicht. So bleibt er immer passend zur installierten Version.
import { copyFileSync, mkdirSync } from "node:fs";

mkdirSync("public/vendor", { recursive: true });
copyFileSync("node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs", "public/vendor/maplibre-gl-worker.mjs");
