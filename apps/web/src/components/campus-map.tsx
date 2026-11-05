"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { BoxIcon, LoaderCircleIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

// Die Kartenbibliothek ist groß. Sie lädt erst nach dem Klick, ebenso die Kartendaten von
// OpenFreeMap: Ohne Klick geht keine Anfrage an den Kartenanbieter.
const CampusMapCanvas = dynamic(() => import("@/components/campus-map-canvas"), {
  ssr: false,
  loading: () => (
    <div className="grid h-[28rem] place-items-center rounded-2xl border max-md:h-96" role="status">
      <span className="inline-flex items-center gap-2 text-sm">
        <LoaderCircleIcon className="size-4 animate-spin" />
        Karte wird geladen
      </span>
    </div>
  ),
});

export function CampusMap({ dataUrl }: { dataUrl: string }) {
  const [open, setOpen] = useState(false);

  return (
    <section className="mt-12">
      <h2 className="text-xl font-semibold">Campus und Wohnen in 3D</h2>
      <p className="mt-1 text-sm">
        Sieh dir an, wo die Gebäude und Wohnheime liegen. Die Angaben stammen aus OpenStreetMap und
        können unvollständig sein.
      </p>
      <div className="mt-4">
        {open ? (
          <CampusMapCanvas dataUrl={dataUrl} />
        ) : (
          <div className="flex flex-col items-start gap-3 rounded-2xl border p-5">
            <p className="text-sm">
              Die Karte lädt Kartendaten von OpenFreeMap. Dabei wird deine IP-Adresse an den Anbieter
              übertragen.
            </p>
            <Button onClick={() => setOpen(true)}>
              <BoxIcon data-icon="inline-start" />
              3D-Karte laden
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
