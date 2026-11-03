"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CircleUserRoundIcon, MenuIcon } from "lucide-react";
import { Logo } from "@/components/logo";
import { CtaButton } from "@/components/cta-button";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/hochschulen", label: "Hochschulen" },
  { href: "/#vorhaben", label: "Was kommt" },
  { href: "/#prinzipien", label: "Prinzipien" },
];

// Anmeldestatus im Browser: bei jedem Seitenwechsel und bei Auth-Ereignissen neu prüfen
function useSignedIn(pathname: string) {
  const [signedIn, setSignedIn] = useState(false);
  useEffect(() => {
    const supabase = createClient();
    supabase.auth
      .getSession()
      .then(({ data }) => setSignedIn(Boolean(data.session)));
    const { data } = supabase.auth.onAuthStateChange((_, session) =>
      setSignedIn(Boolean(session)),
    );
    return () => data.subscription.unsubscribe();
  }, [pathname]);
  return signedIn;
}

export function SiteHeader() {
  const pathname = usePathname();
  const isHome = pathname === "/";
  const signedIn = useSignedIn(pathname);
  const [scrolled, setScrolled] = useState(false);

  // Auf der Startseite erscheint der CTA erst, wenn der Einstieg verlassen ist
  useEffect(() => {
    if (!isHome) return;
    const update = () => setScrolled(window.scrollY > window.innerHeight * 0.5);
    const frame = requestAnimationFrame(update);
    window.addEventListener("scroll", update, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", update);
    };
  }, [isHome]);
  const showCta = !isHome || scrolled;

  return (
    <header className="sticky top-0 z-40 px-3 pt-3 sm:px-6 sm:pt-4">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between rounded-full border bg-background/90 pr-2 pl-5 shadow-sm backdrop-blur">
        <Logo />

        <nav className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <Button
              key={l.href}
              variant="ghost"
              className="rounded-full"
              nativeButton={false}
              render={<Link href={l.href} />}
            >
              {l.label}
            </Button>
          ))}
        </nav>

        <div className="hidden items-center gap-1 md:flex">
          {signedIn ? (
            <Button
              variant="ghost"
              className="rounded-full"
              nativeButton={false}
              render={<Link href="/konto" />}
            >
              <CircleUserRoundIcon data-icon="inline-start" />
              Mein Konto
            </Button>
          ) : (
            <>
              <Button
                variant="ghost"
                className="rounded-full"
                nativeButton={false}
                render={<Link href="/anmelden" />}
              >
                Anmelden
              </Button>
              <Button
                variant="outline"
                className="rounded-full"
                nativeButton={false}
                render={<Link href="/registrieren" />}
              >
                Registrieren
              </Button>
            </>
          )}
          <div
            className={cn(
              "grid transition-all duration-500",
              showCta
                ? "ml-1 grid-cols-[1fr] opacity-100"
                : "pointer-events-none grid-cols-[0fr] opacity-0",
            )}
            aria-hidden={!showCta}
          >
            <div className="overflow-hidden">
              <CtaButton href="/hochschulen" className="h-10 whitespace-nowrap">
                Hochschule finden
              </CtaButton>
            </div>
          </div>
        </div>

        <Sheet>
          <SheetTrigger
            render={
              <Button
                variant="ghost"
                size="icon"
                className="rounded-full md:hidden"
                aria-label="Menü öffnen"
              />
            }
          >
            <MenuIcon />
          </SheetTrigger>
          <SheetContent side="right">
            <SheetHeader>
              <SheetTitle>Menü</SheetTitle>
            </SheetHeader>
            <nav className="flex flex-col gap-1 px-4">
              {LINKS.map((l) => (
                <SheetClose
                  key={l.href}
                  nativeButton={false}
                  render={
                    <Button
                      variant="ghost"
                      className="justify-start"
                      nativeButton={false}
                      render={<Link href={l.href} />}
                    />
                  }
                >
                  {l.label}
                </SheetClose>
              ))}
            </nav>
            <div className="mt-auto grid gap-2 p-4">
              {signedIn ? (
                <SheetClose
                  nativeButton={false}
                  render={
                    <Button
                      nativeButton={false}
                      render={<Link href="/konto" />}
                    />
                  }
                >
                  Mein Konto
                </SheetClose>
              ) : (
                <>
                  <SheetClose
                    nativeButton={false}
                    render={
                      <Button
                        variant="outline"
                        nativeButton={false}
                        render={<Link href="/anmelden" />}
                      />
                    }
                  >
                    Anmelden
                  </SheetClose>
                  <SheetClose
                    nativeButton={false}
                    render={
                      <Button
                        nativeButton={false}
                        render={<Link href="/registrieren" />}
                      />
                    }
                  >
                    Registrieren
                  </SheetClose>
                </>
              )}
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
