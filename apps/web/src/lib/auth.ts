// Nur interne Pfade als Weiterleitungsziel zulassen (kein Open Redirect)
export function safeNext(next: string | null | undefined, fallback = "/konto") {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : fallback;
}

// Supabase-Fehlermeldungen in verständliches Deutsch übersetzen
export function authErrorMessage(code: string | undefined, message: string) {
  switch (code) {
    case "invalid_credentials":
      return "E-Mail oder Passwort ist falsch.";
    case "email_not_confirmed":
      return "Bitte bestätige zuerst deine E-Mail-Adresse. Den Link findest du in deinem Postfach.";
    case "user_already_exists":
    case "email_exists":
      return "Für diese E-Mail gibt es schon ein Konto. Melde dich an oder setze dein Passwort zurück.";
    case "weak_password":
      return "Das Passwort ist zu schwach. Nimm mindestens 8 Zeichen.";
    case "same_password":
      return "Das neue Passwort muss sich vom alten unterscheiden.";
    case "over_email_send_rate_limit":
    case "over_request_rate_limit":
      return "Zu viele Versuche. Warte kurz und versuch es dann noch einmal.";
    case "email_address_invalid":
      return "Diese E-Mail-Adresse ist ungültig.";
    default:
      console.error("Supabase Auth:", code, message);
      return "Das hat nicht geklappt. Versuch es gleich noch einmal.";
  }
}

export type FormState = { error?: string; success?: string } | undefined;
