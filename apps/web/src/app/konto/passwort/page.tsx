import type { Metadata } from "next";
import Link from "next/link";
import { NewPasswordForm } from "@/components/password-forms";

export const metadata: Metadata = {
  title: "Neues Passwort",
  robots: { index: false },
};

// Ziel des Links aus der „Passwort vergessen“-Mail (Sitzung kommt über /auth/callback)
export default function NewPasswordPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center p-6 md:p-10">
      <div className="flex w-full max-w-md flex-col gap-4">
        <NewPasswordForm title="Neues Passwort festlegen" description="Wähle ein Passwort mit mindestens 8 Zeichen." />
        <Link href="/konto" className="text-center text-sm underline-offset-4 hover:underline">
          Weiter zu meinem Konto
        </Link>
      </div>
    </main>
  );
}
