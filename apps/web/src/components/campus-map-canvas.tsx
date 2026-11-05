"use client";

import { useEffect, useRef, useState } from "react";
import { LngLatBounds, Map as MapLibreMap, NavigationControl, Popup, setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { BedDoubleIcon, BuildingIcon, LoaderCircleIcon, TriangleAlertIcon } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

const STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";
const COLORS = { university: "#1ea97b", dormitory: "#2180e6" }; // Marken-Smaragd und Marken-Blau
const PITCH_3D = 58;

setWorkerUrl("/vendor/maplibre-gl-worker.mjs"); // siehe scripts/copy-map-worker.mjs

type CampusFeature = {
  properties: { kind: keyof typeof COLORS; name: string; height: number };
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
};

function boundsOf(features: CampusFeature[]) {
  const bounds = new LngLatBounds();
  const add = (value: unknown[]) => {
    if (typeof value[0] === "number") bounds.extend(value as [number, number]);
    else value.forEach((inner) => add(inner as unknown[]));
  };
  features.forEach((f) => add(f.geometry.coordinates));
  return bounds;
}

export default function CampusMapCanvas({ dataUrl }: { dataUrl: string }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [features, setFeatures] = useState<CampusFeature[]>([]);
  const [is3d, setIs3d] = useState(true);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let created: MapLibreMap | null = null;

    fetch(dataUrl)
      .then((res) => {
        if (!res.ok) throw new Error(`Campus-Daten: ${res.status}`);
        return res.json();
      })
      .then((data: { features: CampusFeature[] }) => {
        if (cancelled || !container.current) return;
        setFeatures(data.features);
        const map = new MapLibreMap({
          container: container.current,
          style: STYLE_URL,
          bounds: boundsOf(data.features),
          fitBoundsOptions: { padding: 40 },
          pitch: PITCH_3D,
          bearing: -24,
          maxPitch: 70,
          cooperativeGestures: true, // Scrollen und Wischen bewegen die Seite, nicht die Karte
          attributionControl: { compact: true, customAttribution: "Campus: © OpenStreetMap-Mitwirkende" },
          locale: {
            "NavigationControl.ZoomIn": "Vergrößern",
            "NavigationControl.ZoomOut": "Verkleinern",
            "NavigationControl.ResetBearing": "Ansicht nach Norden ausrichten",
            "CooperativeGesturesHandler.WindowsHelpText": "Strg + Scrollen zoomt die Karte",
            "CooperativeGesturesHandler.MacHelpText": "⌘ + Scrollen zoomt die Karte",
            "CooperativeGesturesHandler.MobileHelpText": "Mit zwei Fingern bewegst du die Karte",
          },
        });
        created = map;
        mapRef.current = map;
        map.addControl(new NavigationControl({ visualizePitch: true }), "top-right");
        map.on("error", (event) => console.error("Karte:", event.error));

        map.once("idle", () => setReady(true)); // Erst jetzt ist die Karte wirklich gezeichnet
        map.on("load", () => {
          map.addSource("campus", { type: "geojson", data: dataUrl });
          map.addLayer({
            id: "campus-buildings",
            type: "fill-extrusion",
            source: "campus",
            paint: {
              "fill-extrusion-color": ["match", ["get", "kind"], "dormitory", COLORS.dormitory, COLORS.university],
              // Etwas höher als das graue Gebäude der Grundkarte, damit die Farbe oben liegt
              "fill-extrusion-height": ["+", ["get", "height"], 1],
              "fill-extrusion-opacity": 0.95,
            },
          });
          const popup = new Popup({ closeButton: false, offset: 8 });
          map.on("click", "campus-buildings", (event) => {
            const name = event.features?.[0]?.properties?.name;
            if (name) popup.setLngLat(event.lngLat).setText(String(name)).addTo(map);
          });
          map.on("mouseenter", "campus-buildings", () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", "campus-buildings", () => {
            map.getCanvas().style.cursor = "";
          });
        });
      })
      .catch((error) => {
        // Häufigster Fall: Das Gerät unterstützt kein WebGL
        console.error("Karte konnte nicht geladen werden:", error);
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      (created as MapLibreMap | null)?.remove();
      mapRef.current = null;
    };
  }, [dataUrl]);

  function toggle3d() {
    const next = !is3d;
    setIs3d(next);
    mapRef.current?.easeTo({ pitch: next ? PITCH_3D : 0, bearing: next ? -24 : 0, duration: 600 });
  }

  if (failed) {
    return (
      <Alert variant="destructive">
        <TriangleAlertIcon />
        <AlertTitle>Die Karte konnte nicht geladen werden</AlertTitle>
        <AlertDescription>Dein Browser unterstützt sie vielleicht nicht. Versuch es gleich noch einmal.</AlertDescription>
      </Alert>
    );
  }

  const list = (kind: keyof typeof COLORS) =>
    features
      .filter((f) => f.properties.kind === kind)
      .map((f) => f.properties.name)
      .filter((name, index, all) => name !== "Hochschulgebäude" && all.indexOf(name) === index) // Gebäude ohne Namen nur auf der Karte
      .sort((a, b) => a.localeCompare(b, "de", { numeric: true }));

  return (
    <div>
      <div className="relative">
        <div
          ref={container}
          className="h-[28rem] w-full overflow-hidden rounded-2xl border max-md:h-96 max-md:[&_.maplibregl-ctrl-group_button]:size-10!"
          role="application"
          aria-label="3D-Karte des Campus. Die Gebäude stehen auch in der Liste unter der Karte."
        />
        {!ready && (
          <div
            className="pointer-events-none absolute inset-0 grid place-items-center rounded-2xl bg-background/80"
            role="status"
          >
            <span className="inline-flex items-center gap-2 text-sm">
              <LoaderCircleIcon className="size-4 animate-spin" />
              Karte wird geladen
            </span>
          </div>
        )}
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <li className="inline-flex items-center gap-1.5">
            <span className="size-3 rounded-sm" style={{ background: COLORS.university }} aria-hidden />
            <BuildingIcon className="size-3.5" aria-hidden />
            Hochschulgebäude
          </li>
          <li className="inline-flex items-center gap-1.5">
            <span className="size-3 rounded-sm" style={{ background: COLORS.dormitory }} aria-hidden />
            <BedDoubleIcon className="size-3.5" aria-hidden />
            Wohnheime
          </li>
        </ul>
        <Button variant="outline" size="sm" onClick={toggle3d} aria-pressed={is3d}>
          {is3d ? "Von oben ansehen" : "In 3D ansehen"}
        </Button>
      </div>
      {features.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer py-2 font-medium">Gebäude und Wohnheime als Liste</summary>
          <div className="mt-2 grid gap-4 sm:grid-cols-2">
            <div>
              <h3 className="font-medium">Hochschulgebäude</h3>
              <ul className="mt-1 list-disc pl-5">
                {list("university").map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-medium">Wohnheime</h3>
              <ul className="mt-1 list-disc pl-5">
                {list("dormitory").map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            </div>
          </div>
        </details>
      )}
    </div>
  );
}
