# Pathly-Figur

Eigene 3D-Figur, im Code modelliert (Three.js), nicht KI-generiert.

Neu rendern oder ändern (Pose, Farben, Requisiten in `figur-render.html`):

1. `node docs/brand/figur/figur-server.mjs`
2. <http://localhost:3456> öffnen, bis der Tab-Titel „Gespeichert“ zeigt. Das Bild liegt dann als `figur-roh.png` hier im Ordner.
3. Transparenten Rand abschneiden und als `apps/web/public/images/figur/pathly-figur.webp` ablegen (900 px hoch).
4. Falls sich das Seitenverhältnis ändert: `PATHLY_FIGURE_RATIO` in `apps/web/src/components/pathly-figure.tsx` anpassen.
