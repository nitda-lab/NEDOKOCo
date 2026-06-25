import { Header } from "@/components/Header";
import { SortTabs } from "@/components/SortTabs";
import { WorldCard } from "@/components/WorldCard";
import { getPickupWorlds, getWorlds, type SortKey } from "@/lib/worlds";

export const dynamic = "force-dynamic";
const PAGE_SIZE = 24;
const SORTS: SortKey[] = ["updated", "popularity", "favorites"];

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ sort?: string; page?: string }>;
}) {
  const sp = await searchParams;
  const sort: SortKey = SORTS.includes(sp.sort as SortKey) ? (sp.sort as SortKey) : "updated";
  const page = Math.max(1, parseInt(sp.page || "1", 10) || 1);

  const [pickup, worlds] = await Promise.all([
    page === 1 ? getPickupWorlds(6) : Promise.resolve([]),
    getWorlds(sort, PAGE_SIZE, (page - 1) * PAGE_SIZE),
  ]);

  const grid = "grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3";

  return (
    <>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-6">
        {page === 1 && pickup.length > 0 && (
          <section className="mb-8">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-bold text-accent">ランダムピックアップ</h2>
              <a href="/" className="text-sm opacity-70 hover:opacity-100">シャッフル ↻</a>
            </div>
            <div className="flex gap-4 overflow-x-auto pb-2">
              {pickup.map((w) => (
                <div key={`p-${w.world_id}`} className="w-60 shrink-0">
                  <WorldCard world={w} />
                </div>
              ))}
            </div>
          </section>
        )}

        <section>
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-bold">ぶい睡ワールド</h2>
            <SortTabs active={sort} />
          </div>
          {worlds.length === 0 ? (
            <p className="opacity-70">ワールドがまだありません。しばらくお待ちください…</p>
          ) : (
            <div className={grid}>
              {worlds.map((w) => (
                <WorldCard key={w.world_id} world={w} />
              ))}
            </div>
          )}

          <div className="mt-6 flex justify-end gap-4">
            {page > 1 && (
              <a className="text-accent" href={`/?sort=${sort}&page=${page - 1}`}>← 前へ</a>
            )}
            {worlds.length === PAGE_SIZE && (
              <a className="text-accent" href={`/?sort=${sort}&page=${page + 1}`}>次へ →</a>
            )}
          </div>
        </section>
      </main>
    </>
  );
}
