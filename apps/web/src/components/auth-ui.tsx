"use client";

import { useFormStatus } from "react-dom";
import { CircleAlertIcon, CircleCheckIcon, LoaderCircleIcon } from "lucide-react";
import { signInWithGoogle } from "@/app/auth/actions";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { FormState } from "@/lib/auth";

// Rückmeldung eines Formulars (Fehler oder Erfolg)
export function FormMessage({ state }: { state: FormState }) {
  if (!state?.error && !state?.success) return null;
  const isError = Boolean(state.error);
  return (
    <Alert
      variant={isError ? "destructive" : "default"}
      className={isError ? undefined : "border-brand-mint bg-brand-mint/40"}
      aria-live="polite"
    >
      {isError ? <CircleAlertIcon /> : <CircleCheckIcon />}
      <AlertDescription className={isError ? undefined : "text-primary"}>
        {state.error ?? state.success}
      </AlertDescription>
    </Alert>
  );
}

// Absende-Button mit Ladezustand
export function SubmitButton({
  children,
  variant,
}: {
  children: React.ReactNode;
  variant?: "default" | "destructive";
}) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" variant={variant} disabled={pending} aria-busy={pending}>
      {pending && <LoaderCircleIcon className="animate-spin" data-icon="inline-start" />}
      {children}
    </Button>
  );
}

function GoogleIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden>
      <path
        d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
        fill="currentColor"
      />
    </svg>
  );
}

function GoogleSubmit({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <Button variant="outline" type="submit" className="w-full" disabled={pending}>
      {pending ? <LoaderCircleIcon className="animate-spin" /> : <GoogleIcon />}
      {label}
    </Button>
  );
}

// Eigenes Formular, damit es nicht im E-Mail-Formular verschachtelt ist
export function GoogleButton({ label, next }: { label: string; next?: string }) {
  return (
    <form action={signInWithGoogle}>
      {next && <input type="hidden" name="weiter" value={next} />}
      <GoogleSubmit label={label} />
    </form>
  );
}
