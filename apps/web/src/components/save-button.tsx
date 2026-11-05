"use client";

import Link from "next/link";
import { useOptimistic, useState, useTransition } from "react";
import { BookmarkIcon } from "lucide-react";
import { setSaved } from "@/app/hochschulen/actions";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function SaveButton({
  universityId,
  universityName,
  saved,
  signedIn,
  compact = false,
  className,
}: {
  universityId: number;
  universityName: string;
  saved: boolean;
  signedIn: boolean;
  // Nur das Symbol, z. B. auf den Karten der Hochschulsuche
  compact?: boolean;
  className?: string;
}) {
  const [optimistic, setOptimistic] = useOptimistic(saved);
  const [error, setError] = useState<string>();
  const [, startTransition] = useTransition();

  const size = compact ? "icon" : "lg";
  const sizing = compact ? undefined : "h-10 px-4";
  const label = `${universityName} ${optimistic ? "von der Merkliste entfernen" : "merken"}`;

  if (!signedIn) {
    return (
      <Button
        variant="outline"
        size={size}
        className={cn(sizing, className)}
        nativeButton={false}
        aria-label={`${universityName} merken (Anmeldung nötig)`}
        render={<Link href={`/anmelden?weiter=/hochschulen/${universityId}`} />}
      >
        <BookmarkIcon data-icon={compact ? undefined : "inline-start"} />
        {!compact && "Merken"}
      </Button>
    );
  }

  const toggle = () => {
    const next = !saved;
    setError(undefined);
    startTransition(async () => {
      setOptimistic(next);
      const result = await setSaved(universityId, next);
      if (result.error) setError(result.error);
    });
  };

  return (
    <span className={cn("inline-flex flex-col items-start gap-1", className)}>
      <Button
        type="button"
        variant={optimistic ? "secondary" : "outline"}
        size={size}
        className={sizing}
        aria-pressed={optimistic}
        aria-label={label}
        title={compact ? error : undefined}
        onClick={toggle}
      >
        <BookmarkIcon
          data-icon={compact ? undefined : "inline-start"}
          className={optimistic ? "fill-current" : undefined}
        />
        {!compact && (optimistic ? "Gemerkt" : "Merken")}
      </Button>
      {/* Bei wenig Platz bleibt nur der Hinweis für Screenreader und der Tooltip */}
      <span role="status" className={compact ? "sr-only" : "text-sm text-destructive"}>
        {error}
      </span>
    </span>
  );
}
