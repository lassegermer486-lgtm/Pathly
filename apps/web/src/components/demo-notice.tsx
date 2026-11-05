import { FlaskConicalIcon } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export function DemoNotice({ className }: { className?: string }) {
  return (
    <Alert className={className}>
      <FlaskConicalIcon />
      <AlertTitle>Demodaten</AlertTitle>
      <AlertDescription>
        Diese Hochschulen und Studiengänge sind erfunden. Die Seite dient nur dazu,
        die Funktion zu entwerfen und zu testen.
      </AlertDescription>
    </Alert>
  );
}
