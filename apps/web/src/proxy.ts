import type { NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/proxy";

export async function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  // Alles außer statischen Dateien, Bildern und Icons
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|icon.png|apple-icon.png|opengraph-image.png|brand/|robots.txt|sitemap.xml|.*\\.(?:svg|png|jpg|jpeg|gif|webp|geojson|mjs)$).*)",
  ],
};
