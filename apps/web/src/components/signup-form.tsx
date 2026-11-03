import Link from "next/link"
import { cn } from "cn"

import { AccountsComingSoon } from "@/components/accounts-coming-soon"
import { Button } from "@/components/ui/button"
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
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"

export function SignupForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card>
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Konto erstellen</CardTitle>
          <CardDescription>
            Speichere Hochschulen und vergleiche sie später in Ruhe
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <AccountsComingSoon />
          <form>
            <fieldset disabled className="disabled:opacity-60">
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="name">Name</FieldLabel>
                  <Input id="name" type="text" placeholder="Alex Muster" required />
                </Field>
                <Field>
                  <FieldLabel htmlFor="email">E-Mail</FieldLabel>
                  <Input
                    id="email"
                    type="email"
                    placeholder="name@beispiel.de"
                    required
                  />
                </Field>
                <Field>
                  <Field className="grid grid-cols-2 gap-4">
                    <Field>
                      <FieldLabel htmlFor="password">Passwort</FieldLabel>
                      <Input id="password" type="password" required />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor="confirm-password">
                        Wiederholen
                      </FieldLabel>
                      <Input id="confirm-password" type="password" required />
                    </Field>
                  </Field>
                  <FieldDescription>
                    Mindestens 8 Zeichen.
                  </FieldDescription>
                </Field>
                <Field>
                  <Button type="submit">Konto erstellen</Button>
                </Field>
              </FieldGroup>
            </fieldset>
          </form>
          <FieldDescription className="text-center">
            Schon ein Konto? <Link href="/anmelden">Anmelden</Link>
          </FieldDescription>
        </CardContent>
      </Card>
      <FieldDescription className="px-6 text-center">
        Mit der Registrierung stimmst du unserer{" "}
        <Link href="/datenschutz">Datenschutzerklärung</Link> zu.
      </FieldDescription>
    </div>
  )
}
