import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { BookmarkIcon, LogOutIcon, MailIcon, TriangleAlertIcon, UserRoundIcon } from "lucide-react";
import { logout } from "@/app/auth/actions";
import { DeleteAccountForm } from "@/components/delete-account-form";
import { NewPasswordForm } from "@/components/password-forms";
import { SaveButton } from "@/components/save-button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Item, ItemActions, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item";
import { createClient } from "@/lib/supabase/server";
import { INSTITUTION_TYPES, PUBLIC_MARKET_ACCESS } from "@/lib/universities";

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

  // Nur Hochschulen, die aktuell öffentlich sichtbar sind
  const { data: savedRows, error: savedError } = await supabase
    .from("saved_universities")
    .select("university:universities!inner(id, name, institution_type)")
    .overlaps("university.market_access", PUBLIC_MARKET_ACCESS)
    .order("created_at", { ascending: false });
  if (savedError) console.error("saved_universities:", savedError.message);
  const savedUniversities = (savedRows ?? []).map(
    (row) => row.university as unknown as { id: number; name: string; institution_type: string }
  );

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
          <CardTitle>Merkliste</CardTitle>
          <CardDescription>Hochschulen, die du dir gemerkt hast.</CardDescription>
        </CardHeader>
        <CardContent>
          {savedError ? (
            <Alert variant="destructive">
              <TriangleAlertIcon />
              <AlertTitle>Merkliste konnte nicht geladen werden</AlertTitle>
              <AlertDescription>Versuch es gleich noch einmal.</AlertDescription>
            </Alert>
          ) : savedUniversities.length === 0 ? (
            <Empty className="border">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <BookmarkIcon />
                </EmptyMedia>
                <EmptyTitle>Noch nichts gemerkt</EmptyTitle>
                <EmptyDescription>
                  Merke dir Hochschulen in der Suche, dann findest du sie hier wieder.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent>
                <Button variant="outline" nativeButton={false} render={<Link href="/hochschulen" />}>
                  Hochschulen ansehen
                </Button>
              </EmptyContent>
            </Empty>
          ) : (
            <ItemGroup className="gap-2">
              {savedUniversities.map((u) => (
                <Item key={u.id} variant="muted" className="relative">
                  <ItemContent>
                    <ItemTitle>
                      {/* Die ganze Zeile ist antippbar */}
                      <Link
                        href={`/hochschulen/${u.id}`}
                        className="after:absolute after:inset-0 hover:text-accent-foreground"
                      >
                        {u.name}
                      </Link>
                    </ItemTitle>
                    {INSTITUTION_TYPES[u.institution_type] && (
                      <ItemDescription>{INSTITUTION_TYPES[u.institution_type]}</ItemDescription>
                    )}
                  </ItemContent>
                  <ItemActions className="relative z-10">
                    <SaveButton compact universityId={u.id} universityName={u.name} saved signedIn />
                  </ItemActions>
                </Item>
              ))}
            </ItemGroup>
          )}
        </CardContent>
      </Card>

      <Card className="mt-6">
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
