import { CircleAlertIcon, CircleCheckIcon, CircleDashedIcon, CircleXIcon } from "lucide-react";
import type { CheckStatus, Fit } from "@/lib/admission";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Immer Symbol und Text, damit die Aussage nicht nur an der Farbe hängt
export const STATUS_ICONS: Record<CheckStatus, typeof CircleCheckIcon> = {
  met: CircleCheckIcon,
  partial: CircleAlertIcon,
  unmet: CircleXIcon,
  unknown: CircleDashedIcon,
};

export const STATUS_COLORS: Record<CheckStatus, string> = {
  met: "text-brand-primary",
  partial: "text-brand-olive",
  unmet: "text-destructive",
  unknown: "text-muted-foreground",
};

const FITS: Partial<Record<Fit, { label: string; icon: typeof CircleCheckIcon; className: string }>> = {
  likely: { label: "Passt voraussichtlich", icon: CircleCheckIcon, className: "bg-brand-mint text-brand-primary" },
  partial: { label: "Teilweise erfüllt", icon: CircleAlertIcon, className: "bg-brand-cream text-brand-olive" },
  unlikely: { label: "Eher nicht erfüllt", icon: CircleXIcon, className: "bg-destructive/10 text-destructive" },
  incomplete: { label: "Bisher keine Lücke", icon: CircleDashedIcon, className: "bg-muted text-muted-foreground" },
};

export function FitBadge({ fit, className }: { fit: Fit; className?: string }) {
  const config = FITS[fit];
  if (!config) return null;
  const Icon = config.icon;
  return (
    <Badge className={cn("h-auto whitespace-normal", config.className, className)}>
      <Icon />
      {config.label}
    </Badge>
  );
}
