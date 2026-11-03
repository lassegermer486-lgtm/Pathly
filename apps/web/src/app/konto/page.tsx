import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { LogOutIcon, MailIcon, UserRoundIcon } from "lucide-react";
import { logout } from "@/app/auth/actions";
import { DeleteAccountForm } from "@/components/delete-account-form";
import { NewPasswordForm } from "@/components/password-forms";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Item, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Mein Konto",
  robots: { index: false },
};

export default async function AccountPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/anmelden?weiter=/konto");

  const name = (user.user_metadata.full_name ?? user.user_metadata.name) as string | undefined;
  const viaGoogle = user.app_metadata.provider === "google";
  const since = new Date(user.created_at).toLocaleDateString("de-DE");

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl tracking-tight text-primary">Mein Konto</h1>
          <p className="mt-2 text-muted-foreground">Dabei seit {since}</p>
        </div>
        <form action={logout}>
          <Button type="submit" variant="outline" className="rounded-full">
            <LogOutIcon data-icon="inline-start" />
            Abmelden
          </Button>
        </form>
      </div>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>Profil</CardTitle>
          <CardDescription>So bist du bei Pathly angemeldet.</CardDescription>
        </CardHeader>
        <CardContent>
          <ItemGroup className="gap-2">
            {name && (
              <Item variant="muted">
                <ItemMedia variant="icon">
                  <UserRoundIcon />
                </ItemMedia>
                <ItemContent>
                  <ItemDescription>Name</ItemDescription>
                  <ItemTitle>{name}</ItemTitle>
                </ItemContent>
              </Item>
            )}
            <Item variant="muted">
              <ItemMedia variant="icon">
                <MailIcon />
              </ItemMedia>
              <ItemContent>
                <ItemDescription>E-Mail</ItemDescription>
                <ItemTitle>
                  {user.email}
                  {viaGoogle && <Badge variant="outline">über Google</Badge>}
                </ItemTitle>
              </ItemContent>
            </Item>
          </ItemGroup>
        </CardContent>
      </Card>

      <div className="mt-6">
        <NewPasswordForm
          title={viaGoogle ? "Passwort festlegen" : "Passwort ändern"}
          description={
            viaGoogle
              ? "Optional: Mit einem Passwort kannst du dich auch ohne Google anmelden."
              : "Mindestens 8 Zeichen."
          }
        />
      </div>

      <div className="mt-6">
        <DeleteAccountForm />
      </div>
    </main>
  );
}
