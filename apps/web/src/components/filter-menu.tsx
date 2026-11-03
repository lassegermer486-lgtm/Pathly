"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ChevronDownIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

// Mehrfach-Filter der Hochschulsuche. Jede Änderung schreibt die Auswahl als
// kommagetrennte Liste in die URL (Suchbegriff und andere Filter bleiben).
// Das versteckte Feld sorgt dafür, dass ein Absenden des Suchfelds den Filter mitschickt.
export function FilterMenu({
  name,
  label,
  allLabel,
  options,
  value,
}: {
  name: string;
  label: string;
  allLabel: string;
  options: Record<string, string>;
  value: string[];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const selected = value.filter((v) => v in options);

  function apply(next: string[]) {
    const params = new URLSearchParams(searchParams);
    if (next.length) params.set(name, next.join(","));
    else params.delete(name);
    params.delete("seite");
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  function toggle(key: string, checked: boolean) {
    // Reihenfolge wie im Menü, damit die URL stabil bleibt
    const set = new Set(selected);
    if (checked) set.add(key);
    else set.delete(key);
    apply(Object.keys(options).filter((k) => set.has(k)));
  }

  const summary =
    selected.length === 0
      ? allLabel
      : selected.length === 1
        ? options[selected[0]]
        : `${options[selected[0]]} +${selected.length - 1}`;

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium">{label}</span>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="outline"
              className={cn(
                "h-9 w-full justify-between rounded-lg font-normal",
                selected.length > 0 && "border-primary/30 bg-brand-mint/40 text-primary"
              )}
              aria-label={`${label}: ${selected.length ? selected.map((k) => options[k]).join(", ") : allLabel}`}
            >
              <span className="truncate">{summary}</span>
              <ChevronDownIcon className="text-muted-foreground" />
            </Button>
          }
        />
        <DropdownMenuContent className="max-h-80 w-(--anchor-width) min-w-60" align="start">
          <DropdownMenuGroup>
            <DropdownMenuLabel>
              {label}
              {selected.length > 0 && ` · ${selected.length} gewählt`}
            </DropdownMenuLabel>
            {selected.length > 0 && (
              <DropdownMenuItem onClick={() => apply([])}>
                <XIcon />
                Auswahl aufheben
              </DropdownMenuItem>
            )}
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            {Object.entries(options).map(([key, text]) => (
              <DropdownMenuCheckboxItem
                key={key}
                checked={selected.includes(key)}
                onCheckedChange={(checked) => toggle(key, checked)}
              >
                {text}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {selected.length > 0 && <input type="hidden" name={name} value={selected.join(",")} />}
    </div>
  );
}
