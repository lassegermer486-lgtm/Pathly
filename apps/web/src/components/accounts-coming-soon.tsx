import { SparklesIcon } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

// Konten gibt es noch nicht – bis dahin sind die Formulare nur Vorschau.
export function AccountsComingSoon() {
  return (
    <Alert className="border-brand-mint bg-brand-mint/40">
      <SparklesIcon />
      <AlertTitle>Konten starten bald</AlertTitle>
      <AlertDescription>
        Bald kannst du Hochschulen merken und vergleichen. Die Suche funktioniert
        schon heute ohne Konto.
      </AlertDescription>
    </Alert>
  );
}
