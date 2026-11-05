// Kleiner Hilfsserver zum Rendern der Pathly-Figur:
//   node docs/brand/figur/figur-server.mjs
// Dann http://localhost:3456 öffnen. Das Bild wird als figur-roh.png in diesen Ordner geschrieben.
import { readFileSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const logo = join(here, "..", "..", "..", "apps", "web", "public", "brand", "pathly-logo-white.png");

createServer((req, res) => {
  if (req.method === "POST" && req.url === "/save") {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      writeFileSync(join(here, "figur-roh.png"), Buffer.concat(chunks));
      res.end("ok");
    });
    return;
  }
  if (req.url === "/logo-weiss.png") {
    res.setHeader("Content-Type", "image/png");
    return res.end(readFileSync(logo));
  }
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.end(readFileSync(join(here, "figur-render.html")));
}).listen(3456, "127.0.0.1", () => console.log("http://localhost:3456"));
