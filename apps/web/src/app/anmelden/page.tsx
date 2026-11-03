import type { Metadata } from "next";
import { LoginForm } from "@/components/login-form";

export const metadata: Metadata = {
  title: "Anmelden",
  robots: { index: false },
};

export default function LoginPage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm">
        <LoginForm />
      </div>
    </main>
  );
}
