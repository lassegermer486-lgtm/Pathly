"use client";

import { useActionState } from "react";
import { deleteAccount } from "@/app/auth/actions";
import { FormMessage, SubmitButton } from "@/components/auth-ui";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export function DeleteAccountForm() {
  const [state, action] = useActionState(deleteAccount, undefined);
  return (
    <Card className="ring-destructive/30">
      <CardHeader>
        <CardTitle>Konto löschen</CardTitle>
        <CardDescription>
          Dein Konto und alle damit verbundenen Daten werden sofort und endgültig gelöscht.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <FormMessage state={state} />
        <form action={action}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="bestaetigung">Zur Bestätigung LÖSCHEN eintippen</FieldLabel>
              <Input id="bestaetigung" name="bestaetigung" autoComplete="off" placeholder="LÖSCHEN" required />
              <FieldDescription>Das lässt sich nicht rückgängig machen.</FieldDescription>
            </Field>
            <Field orientation="horizontal">
              <SubmitButton variant="destructive">Konto endgültig löschen</SubmitButton>
            </Field>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  );
}
