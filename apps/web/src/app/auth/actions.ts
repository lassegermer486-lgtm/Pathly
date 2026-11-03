"use server";

import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { authErrorMessage, safeNext, type FormState } from "@/lib/auth";

const MIN_PASSWORD = 8;

// Basis-URL der aktuellen Anfrage – damit Links lokal, in Previews und live stimmen
async function origin() {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  const proto = h.get("x-forwarded-proto") ?? (host?.startsWith("localhost") ? "http" : "https");
  return `${proto}://${host}`;
}

function field(formData: FormData, name: string) {
  const value = formData.get(name);
  return typeof value === "string" ? value.trim() : "";
}

export async function login(_: FormState, formData: FormData): Promise<FormState> {
  const email = field(formData, "email");
  const password = formData.get("password");
  if (!email || typeof password !== "string" || !password) {
    return { error: "Gib deine E-Mail und dein Passwort ein." };
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) return { error: authErrorMessage(error.code, error.message) };

  redirect(safeNext(field(formData, "weiter")));
}

export async function signup(_: FormState, formData: FormData): Promise<FormState> {
  const name = field(formData, "name");
  const email = field(formData, "email");
  const password = formData.get("password");
  const confirm = formData.get("confirm-password");

  if (!email || typeof password !== "string") return { error: "Gib deine E-Mail und ein Passwort ein." };
  if (password.length < MIN_PASSWORD) return { error: `Das Passwort braucht mindestens ${MIN_PASSWORD} Zeichen.` };
  if (password !== confirm) return { error: "Die Passwörter stimmen nicht überein." };

  const supabase = await createClient();
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: name ? { full_name: name } : undefined,
      emailRedirectTo: `${await origin()}/auth/callback?next=/konto`,
    },
  });
  if (error) return { error: authErrorMessage(error.code, error.message) };

  // Ist die E-Mail-Bestätigung in Supabase ausgeschaltet, gibt es sofort eine Sitzung
  if (data.session) redirect("/konto");

  return {
    success: `Fast geschafft: Wir haben dir eine E-Mail an ${email} geschickt. Klick auf den Link darin, um dein Konto zu bestätigen.`,
  };
}

export async function signInWithGoogle(formData: FormData) {
  const next = safeNext(field(formData, "weiter"));
  const supabase = await createClient();
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: `${await origin()}/auth/callback?next=${encodeURIComponent(next)}` },
  });
  if (error || !data.url) redirect("/anmelden?fehler=google");
  redirect(data.url);
}

export async function requestPasswordReset(_: FormState, formData: FormData): Promise<FormState> {
  const email = field(formData, "email");
  if (!email) return { error: "Gib deine E-Mail-Adresse ein." };

  const supabase = await createClient();
  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${await origin()}/auth/callback?next=/konto/passwort`,
  });
  if (error) return { error: authErrorMessage(error.code, error.message) };

  // Bewusst gleiche Antwort, egal ob das Konto existiert
  return { success: `Falls es ein Konto für ${email} gibt, ist eine E-Mail mit einem Link unterwegs.` };
}

export async function updatePassword(_: FormState, formData: FormData): Promise<FormState> {
  const password = formData.get("password");
  const confirm = formData.get("confirm-password");
  if (typeof password !== "string" || password.length < MIN_PASSWORD) {
    return { error: `Das Passwort braucht mindestens ${MIN_PASSWORD} Zeichen.` };
  }
  if (password !== confirm) return { error: "Die Passwörter stimmen nicht überein." };

  const supabase = await createClient();
  const { error } = await supabase.auth.updateUser({ password });
  if (error) return { error: authErrorMessage(error.code, error.message) };
  return { success: "Dein Passwort ist geändert." };
}

export async function logout() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/");
}

export async function deleteAccount(_: FormState, formData: FormData): Promise<FormState> {
  if (field(formData, "bestaetigung") !== "LÖSCHEN") {
    return { error: "Tippe LÖSCHEN ein, um dein Konto endgültig zu löschen." };
  }

  const supabase = await createClient();
  // Datenbankfunktion löscht ausschließlich das Konto des angemeldeten Nutzers
  const { error } = await supabase.rpc("delete_own_account");
  if (error) {
    console.error("delete_own_account:", error.message);
    return { error: "Dein Konto konnte nicht gelöscht werden. Schreib uns an kontakt@pathly.info." };
  }
  await supabase.auth.signOut();
  redirect("/?konto=geloescht");
}
