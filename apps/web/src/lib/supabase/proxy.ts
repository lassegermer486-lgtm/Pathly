import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

// Bereiche, die nur mit Anmeldung erreichbar sind
const PROTECTED = ["/konto"];

// Frischt die Supabase-Sitzung bei jeder Anfrage auf und schreibt die Cookies zurück.
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // Zwischen createServerClient und getClaims darf kein weiterer Code stehen,
  // sonst können Nutzer zufällig abgemeldet werden.
  const { data } = await supabase.auth.getClaims();
  const user = data?.claims;

  const { pathname } = request.nextUrl;
  if (!user && PROTECTED.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    const url = request.nextUrl.clone();
    url.pathname = "/anmelden";
    url.search = `?weiter=${encodeURIComponent(pathname)}`;
    return NextResponse.redirect(url);
  }

  return response;
}
