"use client";

import { useEffect, useRef } from "react";

// Gipfel im Foto hero.jpg (2400 × 1548 px). Das Foto liegt mit object-cover und
// object-position 60 % top im Einstieg, dieselbe Rechnung setzt den Mast auf den Berg.
const PHOTO = { width: 2400, height: 1548 };
const SUMMIT = { x: 1472, y: 280 };
const POSITION_X = 0.6;
const NARROW_BELOW = 1024; // Breite, ab der das Wort hinter dem Berg durchlaufen darf

const FLAG_COLOR = "#cbf39d"; // Marken-Lime: hebt sich von Himmel und dunkler Schrift ab
const POLE_COLOR = "#053438";
const LOGO_SRC = "/brand/pathly-logo.png";
const LOGO_RATIO = 681 / 225;

// Die Flagge entsteht auf einer Zeichenfläche und wird Streifen für Streifen wellenförmig
// verschoben. Sie ist also kein Bild und passt sich jeder Größe an.
export function HeroFlag() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const parent = canvas?.parentElement;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !parent || !ctx) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const flag = document.createElement("canvas");
    const logo = new Image();
    let flagW = 0;
    let flagH = 0;
    let poleH = 0;
    let margin = 0;
    let dpr = 1;
    let frame = 0;
    let visible = true;

    function drawFlagCloth() {
      flag.width = Math.round(flagW * dpr);
      flag.height = Math.round(flagH * dpr);
      const f = flag.getContext("2d");
      if (!f) return;
      f.fillStyle = FLAG_COLOR;
      f.fillRect(0, 0, flag.width, flag.height);
      if (logo.complete && logo.naturalWidth > 0) {
        const logoW = flag.width * 0.74;
        const logoH = logoW / LOGO_RATIO;
        f.drawImage(logo, (flag.width - logoW) / 2, (flag.height - logoH) / 2, logoW, logoH);
      }
    }

    function layout() {
      const cw = parent!.clientWidth;
      const ch = parent!.clientHeight;

      flagW = Math.max(84, Math.min(cw * 0.1, 170));
      flagH = flagW / 1.55;
      poleH = flagH * 1.55;
      margin = flagH * 0.55;
      dpr = Math.min(window.devicePixelRatio || 1, 2);

      // Schmale Bildschirme: Berg so weit nach unten, dass die Flagge unter dem Wort Platz hat.
      // Der Abstand ändert auch den Maßstab des Fotos, darum in wenigen Schritten annähern.
      let offset = 0;
      if (cw < NARROW_BELOW) {
        const word = parent!.querySelector("[data-hero-word]");
        const wordBottom = word
          ? word.getBoundingClientRect().bottom - parent!.getBoundingClientRect().top
          : 0;
        for (let i = 0; i < 4; i++) {
          const s = Math.max(cw / PHOTO.width, (ch - offset) / PHOTO.height);
          offset = Math.max(0, wordBottom + poleH + 8 - SUMMIT.y * s);
        }
      }
      parent!.style.setProperty("--hero-offset", `${offset}px`);

      const scale = Math.max(cw / PHOTO.width, (ch - offset) / PHOTO.height);
      const summitX = (cw - PHOTO.width * scale) * POSITION_X + SUMMIT.x * scale;
      const summitY = offset + SUMMIT.y * scale;

      const width = flagW * 1.1 + margin;
      const height = poleH + margin;
      canvas!.width = Math.round(width * dpr);
      canvas!.height = Math.round(height * dpr);
      canvas!.style.width = `${width}px`;
      canvas!.style.height = `${height}px`;
      // Die untere Spitze des Mastes steht auf dem Gipfel
      canvas!.style.left = `${summitX - margin}px`;
      canvas!.style.top = `${summitY - poleH - margin}px`;
      drawFlagCloth();
      draw(reduceMotion ? 1.2 : performance.now() / 1000);
    }

    function draw(t: number) {
      const c = ctx!;
      c.setTransform(dpr, 0, 0, dpr, 0, 0);
      c.clearRect(0, 0, canvas!.width, canvas!.height);

      const poleX = margin;
      const top = margin;
      const startX = poleX + 1.5;
      const gust = 1 + 0.3 * Math.sin(t * 0.9) + 0.15 * Math.sin(t * 2.3);
      const step = 1 / dpr;
      const cloth = flag.width / flagW;

      // Starker Wind: kurze, schnelle Wellen, die zum freien Ende hin größer werden
      for (let x = 0; x < flagW; x += step) {
        const reach = x / flagW;
        const phase = reach * 9 - t * 11;
        const amp = flagH * 0.27 * gust * (0.08 + reach * reach * 0.75 + reach * 0.35);
        const wave = Math.sin(phase) + 0.35 * Math.sin(phase * 2.1 + 1.3);
        const y = top + amp * wave;
        const squeeze = 1 - 0.1 * reach * (0.5 + 0.5 * Math.sin(phase + 0.9));
        const drawX = startX + x * squeeze;
        c.drawImage(flag, x * cloth, 0, Math.max(step * cloth, 1), flag.height, drawX, y, step + 0.6, flagH);
        // Licht und Schatten auf den Falten
        const slope = Math.cos(phase);
        c.fillStyle = slope > 0 ? `rgba(0, 40, 30, ${slope * 0.3})` : `rgba(255, 255, 255, ${-slope * 0.28})`;
        c.fillRect(drawX, y, step + 0.6, flagH);
      }

      c.strokeStyle = POLE_COLOR;
      c.lineWidth = 3;
      c.lineCap = "round";
      c.beginPath();
      c.moveTo(poleX, top - 5);
      c.lineTo(poleX, top + poleH);
      c.stroke();
    }

    function loop(now: number) {
      if (visible) draw(now / 1000);
      frame = requestAnimationFrame(loop);
    }

    logo.onload = () => {
      drawFlagCloth();
      if (reduceMotion) draw(1.2);
    };
    logo.src = LOGO_SRC;

    const resize = new ResizeObserver(layout);
    resize.observe(parent);
    // Außerhalb des Bildschirms ruht die Animation und spart Akku
    const seen = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
    });
    seen.observe(canvas);
    layout();
    if (!reduceMotion) frame = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      seen.disconnect();
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden className="pointer-events-none absolute -z-[5]" />;
}
