import { BACHELOR_COLUMNS, type BachelorOption } from "@/lib/programs";
import { createClient } from "@/lib/supabase/server";

// Alle Bachelor, deren Studienplan wir kennen. Nur sie stehen in der Auswahl.
export async function getBachelorOptions() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("programs")
    .select(BACHELOR_COLUMNS)
    .eq("degree", "bachelor")
    .neq("curriculum_ects", "{}")
    .order("name");
  if (error) console.error("Bachelor konnten nicht geladen werden:", error);
  return (data ?? []) as unknown as BachelorOption[];
}
