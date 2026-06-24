import { WorldCard } from "@/components/WorldCard";
import { getSuggestedWorlds } from "@/lib/worlds";

export const dynamic = "force-dynamic";

export default async function Home() {
  const worlds = await getSuggestedWorlds(5);
  return (
    <main style={{ maxWidth: 1000, margin: "0 auto", padding: 24 }}>
      <h1 style={{ color: "var(--accent)" }}>🌙 今夜のぶい睡ワールド</h1>
      <p style={{ opacity: 0.8 }}>AI がぶい睡に適したワールドをピックアップしました</p>
      <form>
        <button
          formAction={async () => {
            "use server";
            const { revalidatePath } = await import("next/cache");
            revalidatePath("/");
          }}
          style={{
            background: "var(--accent)", color: "#fff", border: "none",
            borderRadius: 8, padding: "8px 16px", cursor: "pointer", marginBottom: 16,
          }}
        >
          別の 5 件を見る
        </button>
      </form>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 16 }}>
        {worlds.map((w) => (
          <WorldCard key={w.world_id} world={w} />
        ))}
      </div>
      {worlds.length === 0 && <p>ワールドがまだ登録されていません。しばらくお待ちください…</p>}
      <p style={{ marginTop: 24 }}><a href="/worlds">すべてのワールドを見る →</a></p>
    </main>
  );
}
