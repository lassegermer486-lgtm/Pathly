import type { Metadata } from "next";
import { LoginForm } from "@/components/login-form";
import { safeNext } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Anmelden",
  robots: { index: false },
};

export default async function LoginPage({ searchParams }: PageProps<"/anmelden">) {
  const sp = await searchParams;
  const weiter = typeof sp.weiter === "string" ? safeNext(sp.weiter) : undefined;
  const fehler = typeof sp.fehler === "string" ? sp.fehler : undefined;

  return (
    <main className="flex flex-1 flex-col items-center justify-center p-6 md:p-10">
      <div className="w-full max-w-sm">
        <LoginForm next={weiter} linkError={fehler} />
      </div>
    </main>
  );
}
