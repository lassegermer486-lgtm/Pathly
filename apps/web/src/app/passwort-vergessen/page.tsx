import type { Metadata } from "next";
import { ResetRequestForm } from "@/components/password-forms";

export const metadata: Metadata = {
  title: "Passwort vergessen",
  robots: { index: false },
};

export default function ForgotPasswordPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm">
        <ResetRequestForm />
      </div>
    </main>
  );
}
