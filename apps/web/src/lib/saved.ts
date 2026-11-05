import { createClient } from "@/lib/supabase/server";

// Für welche der angezeigten Hochschulen gilt „gemerkt“? Ohne Anmeldung: keine.
export async function getSavedState(universityIds: number[]) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { signedIn: false, saved: new Set<number>() };
  if (universityIds.length === 0) return { signedIn: true, saved: new Set<number>() };

  const { data, error } = await supabase
    .from("saved_universities")
    .select("university_id")
    .in("university_id", universityIds);
  if (error) console.error("saved_universities:", error.message);

  return {
    signedIn: true,
    saved: new Set((data ?? []).map((row) => row.university_id as number)),
  };
}
