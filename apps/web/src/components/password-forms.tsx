"use client";

import { useActionState } from "react";
import Link from "next/link";
import { requestPasswordReset, updatePassword } from "@/app/auth/actions";
import { FormMessage, SubmitButton } from "@/components/auth-ui";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

// Schritt 1: Link zum Zurücksetzen anfordern
export function ResetRequestForm() {
  const [state, action] = useActionState(requestPasswordReset, undefined);
  return (
    <Card>
      <CardHeader className="text-center">
        <CardTitle className="text-xl">Passwort vergessen?</CardTitle>
        <CardDescription>Wir schicken dir einen Link, mit dem du ein neues Passwort setzt.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <FormMessage state={state} />
        {!state?.success && (
          <form action={action}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="email">E-Mail</FieldLabel>
                <Input id="email" name="email" type="email" autoComplete="email" placeholder="name@beispiel.de" required />
              </Field>
              <Field>
                <SubmitButton>Link anfordern</SubmitButton>
              </Field>
            </FieldGroup>
          </form>
        )}
        <FieldDescription className="text-center">
          Doch wieder eingefallen? <Link href="/anmelden">Anmelden</Link>
        </FieldDescription>
      </CardContent>
    </Card>
  );
}

// Schritt 2 (nach dem Link) bzw. Passwort ändern im Konto
export function NewPasswordForm({ title, description }: { title: string; description: string }) {
  const [state, action] = useActionState(updatePassword, undefined);
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <FormMessage state={state} />
        <form action={action}>
          <FieldGroup>
            <Field className="grid gap-4 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="password">Neues Passwort</FieldLabel>
                <Input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required />
              </Field>
              <Field>
                <FieldLabel htmlFor="confirm-password">Wiederholen</FieldLabel>
                <Input
                  id="confirm-password"
                  name="confirm-password"
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  required
                />
              </Field>
            </Field>
            <Field orientation="horizontal">
              <SubmitButton>Passwort speichern</SubmitButton>
            </Field>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
