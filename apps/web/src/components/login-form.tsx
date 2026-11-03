"use client"

import { useActionState } from "react"
import Link from "next/link"
import { cn } from "cn"

import { login } from "@/app/auth/actions"
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

const LINK_ERRORS: Record<string, string> = {
  link: "Der Link ist abgelaufen oder wurde schon benutzt. Melde dich an oder fordere einen neuen an.",
  google: "Die Anmeldung mit Google hat nicht geklappt. Versuch es noch einmal.",
}

export function LoginForm({
  className,
  next,
  linkError,
  ...props
}: React.ComponentProps<"div"> & { next?: string; linkError?: string }) {
  const [state, action] = useActionState(
    login,
    linkError && LINK_ERRORS[linkError] ? { error: LINK_ERRORS[linkError] } : undefined
  )

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card>
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Willkommen zurück</CardTitle>
          <CardDescription>
            Melde dich mit Google oder deiner E-Mail an
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <FormMessage state={state} />
          <GoogleButton label="Mit Google anmelden" next={next} />
          <FieldSeparator className="*:data-[slot=field-separator-content]:bg-card">
            Oder weiter mit E-Mail
          </FieldSeparator>
          <form action={action}>
            {next && <input type="hidden" name="weiter" value={next} />}
            <FieldGroup>
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
                <div className="flex items-center">
                  <FieldLabel htmlFor="password">Passwort</FieldLabel>
                  <Link
                    href="/passwort-vergessen"
                    className="ml-auto text-sm underline-offset-4 hover:underline"
                  >
                    Passwort vergessen?
                  </Link>
                </div>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                />
              </Field>
              <Field>
                <SubmitButton>Anmelden</SubmitButton>
              </Field>
            </FieldGroup>
          </form>
          <FieldDescription className="text-center">
            Noch kein Konto? <Link href="/registrieren">Registrieren</Link>
          </FieldDescription>
        </CardContent>
      </Card>
      <FieldDescription className="px-6 text-center">
        Mit der Anmeldung gilt unsere{" "}
        <Link href="/datenschutz">Datenschutzerklärung</Link>.
      </FieldDescription>
    </div>
  )
}
