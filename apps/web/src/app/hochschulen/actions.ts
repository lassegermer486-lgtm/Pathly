"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";

const FAILED = "Das hat nicht geklappt. Versuch es gleich noch einmal.";

// Hochschule auf die eigene Merkliste setzen oder davon entfernen
export async function setSaved(
  universityId: number,
  saved: boolean
): Promise<{ error?: string }> {
  if (!Number.isSafeInteger(universityId) || universityId <= 0) return { error: FAILED };

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { error: "Melde dich an, um Hochschulen zu merken." };

  const table = supabase.from("saved_universities");
  const { error } = saved
    ? await table.upsert(
        { user_id: user.id, university_id: universityId },
        { onConflict: "user_id,university_id", ignoreDuplicates: true }
      )
    : await table.delete().eq("user_id", user.id).eq("university_id", universityId);

  if (error) {
    console.error("saved_universities:", error.message);
    return { error: FAILED };
  }

  // Suche, Detailseiten und Konto zeigen den Merkstatus
  revalidatePath("/", "layout");
  return {};
}
