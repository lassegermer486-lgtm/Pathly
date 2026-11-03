"use client"

import { useActionState } from "react"
import Link from "next/link"
import { cn } from "cn"

import { signup } from "@/app/auth/actions"
import { FormMessage, GoogleButton, SubmitButton } from "@/components/auth-ui"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldSeparator,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"

export function SignupForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const [state, action] = useActionState(signup, undefined)

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card>
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Konto erstellen</CardTitle>
          <CardDescription>
            Kostenlos – mit Google oder deiner E-Mail
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <FormMessage state={state} />
          {!state?.success && (
            <>
              <GoogleButton label="Mit Google registrieren" />
              <FieldSeparator className="*:data-[slot=field-separator-content]:bg-card">
                Oder mit E-Mail
              </FieldSeparator>
              <form action={action}>
                <FieldGroup>
                  <Field>
                    <FieldLabel htmlFor="name">Name</FieldLabel>
                    <Input id="name" name="name" type="text" autoComplete="name" placeholder="Alex Muster" />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="email">E-Mail</FieldLabel>
                    <Input
                      id="email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      placeholder="name@beispiel.de"
                      required
                    />
                  </Field>
                  <Field>
                    <Field className="grid grid-cols-2 gap-4">
                      <Field>
                        <FieldLabel htmlFor="password">Passwort</FieldLabel>
                        <Input
                          id="password"
                          name="password"
                          type="password"
                          autoComplete="new-password"
                          minLength={8}
                          required
                        />
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
                    <FieldDescription>Mindestens 8 Zeichen.</FieldDescription>
                  </Field>
                  <Field>
                    <SubmitButton>Konto erstellen</SubmitButton>
                  </Field>
                </FieldGroup>
              </form>
            </>
          )}
          <FieldDescription className="text-center">
            Schon ein Konto? <Link href="/anmelden">Anmelden</Link>
          </FieldDescription>
        </CardContent>
      </Card>
      <FieldDescription className="px-6 text-center">
        Mit der Registrierung gilt unsere{" "}
        <Link href="/datenschutz">Datenschutzerklärung</Link>.
      </FieldDescription>
    </div>
  )
}
