import type { MetadataRoute } from "next";
import { createClient } from "@supabase/supabase-js";
import { PUBLIC_MARKET_ACCESS } from "@/lib/universities";

const BASE_URL = "https://pathly.info";

export const revalidate = 86400;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const supabase = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!
  );
  const { data } = await supabase
    .from("universities")
    .select("id, updated_at")
    .overlaps("market_access", PUBLIC_MARKET_ACCESS)
    .limit(5000);

  return [
    { url: BASE_URL, changeFrequency: "weekly", priority: 1 },
    { url: `${BASE_URL}/hochschulen`, changeFrequency: "weekly", priority: 0.9 },
    ...(data ?? []).map((u) => ({
      url: `${BASE_URL}/hochschulen/${u.id}`,
      lastModified: u.updated_at,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    })),
  ];
}
