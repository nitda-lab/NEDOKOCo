import { WorldCard } from "@/components/WorldCard";
import { getQualifiedWorlds } from "@/lib/worlds";

export const dynamic = "force-dynamic";
const PAGE_SIZE = 24;

export default async function Worlds({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const { page } = await searchParams;
  const p = Math.max(1, parseInt(page || "1", 10) || 1);
  const worlds = await getQualifiedWorlds(PAGE_SIZE, (p - 1) * PAGE_SIZE);
  return (
    <main style={{ maxWidth: 1000, margin: "0 auto", padding: 24 }}>
      <h1 style={{ color: "var(--accent)" }}>ぶい睡ワールド一覧</h1>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 16 }}>
        {worlds.map((w) => (
          <WorldCard key={w.world_id} world={w} />
        ))}
      </div>
      <div style={{ marginTop: 24, display: "flex", gap: 12 }}>
        {p > 1 && <a href={`/worlds?page=${p - 1}`}>← 前へ</a>}
        {worlds.length === PAGE_SIZE && <a href={`/worlds?page=${p + 1}`}>次へ →</a>}
      </div>
    </main>
  );
}
