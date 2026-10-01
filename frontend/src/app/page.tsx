import { createClient } from "@/lib/supabase/server";
import { Button } from "@/components/ui/button";

export default async function Home() {
  const supabase = await createClient();
  const { data: universities, error } = await supabase
    .from("universities")
    .select("id, name")
    .limit(10);

  if (error) return <p>Fehler: {error.message}</p>;

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Hochschulen ({universities.length})</h1>
      <ul>
        {universities.map((u) => (
          <li key={u.id}>{u.name}</li>
        ))}
      </ul>
      <Button className="mt-4">Hochschule finden</Button>
    </main>
  );
}