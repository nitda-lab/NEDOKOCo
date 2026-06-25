# ネドココ UI 見直し Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ネドココのUIを統合フィード化し、VRChat指標（更新日・お気に入り・人気）で並び替え＋新着からのランダムピックアップを備え、Tailwindでスマホ対応する。

**Architecture:** Python(収集)がVRChat指標をNeonに保存し、Next.js(`app/`)がそれを読み取り単一フィードで表示。並び替えは `?sort=` クエリ、ランダムは新着上位からの抽出。スタイルはTailwind CSS v4。

**Tech Stack:** Next.js 15 (App Router, TS), Tailwind CSS v4, @vercel/postgres, SQLAlchemy 2.0 + asyncpg(本番)/aiosqlite(テスト), pytest。

## Global Constraints

- 対象ワールド: `ai_sleep_score >= 6 AND ai_is_japanese = 1`（`_SUGGEST_SCORE_MIN = 6`）。
- サイト名: `🌙 ネドココ` / キャッチ: `VRChatのぶい睡ワールドを見つける` / meta説明: `AIがぶい睡（VR睡眠）に向いたVRChatワールドを厳選。新着・人気・お気に入りで探したり、ランダムで出会ったり。`
- 並び替えキー: `updated`(=`vrc_updated_at`) / `popularity` / `favorites`、いずれも降順 `NULLS LAST`、既定 `updated`。
- テーマ色: 背景 `#0f0c1d` / カード `#1a1530` / アクセント `#7b68ee` / 文字 `#e8e6f0`。
- PythonユニットテストはインメモリSQLite。本番はNeon(Postgres)。
- DB操作は `db/repository.py` 経由（既存方針）。コメントは原則書かない。YAGNI。
- `get_random_worlds` は Discord bot が使うため残す。Web側DB読み取りは `lib/worlds.ts`(TS) が直接行う（Python採点関数はWebから使わない）。

---

## File Structure

- `db/models.py` (変更) — `World` に `vrc_updated_at` / `favorites` / `popularity` 追加。
- `db/engine.py` (変更) — `init_db()` に Postgres 用 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`。
- `collector/vrc_client.py` (変更) — `_world_to_dict` で指標を取得。
- `db/repository.py` (変更) — `upsert_world` で指標を保存。
- `postcss.config.mjs` (新規) — Tailwind v4 postcss プラグイン。
- `package.json` (変更) — tailwind 依存追加。
- `app/globals.css` (変更) — Tailwind 読み込み＋テーマ。
- `app/layout.tsx` (変更) — メタ情報（ネドココ）。
- `components/Header.tsx` (新規) — サイトヘッダー。
- `components/WorldCard.tsx` (変更) — Tailwind化＋指標表示。
- `components/SortTabs.tsx` (新規) — 並び替えタブ。
- `lib/worlds.ts` (変更) — 型に指標追加、`getPickupWorlds` / `getWorlds(sort,…)` / 表示ヘルパ。
- `app/page.tsx` (変更) — 統合フィード（ピックアップ＋並び替え＋ページング）。
- `app/worlds/page.tsx` (削除)。
- `tests/test_repository.py` / `tests/test_vrc_client.py` (変更) — 指標保存・取得のテスト。

---

## Task 1: World モデルに指標カラム追加

**Files:**
- Modify: `db/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `World.vrc_updated_at: datetime|None`, `World.favorites: int|None`, `World.popularity: int|None`。

- [ ] **Step 1: 失敗テストを書く** — `tests/test_models.py` の末尾に追記

```python
async def test_world_has_metric_columns(session):
    from datetime import datetime
    from db.models import World
    w = World(
        world_id="wm1", name="n", author_name="a",
        vrc_url="https://vrchat.com/home/world/wm1",
        vrc_updated_at=datetime(2026, 6, 1), favorites=123, popularity=45,
    )
    session.add(w)
    await session.commit()

    from sqlalchemy import select
    row = (await session.execute(select(World).where(World.world_id == "wm1"))).scalar_one()
    assert row.favorites == 123
    assert row.popularity == 45
    assert row.vrc_updated_at.year == 2026
```

- [ ] **Step 2: 実行して失敗を確認**

Run: `python -m pytest tests/test_models.py::test_world_has_metric_columns -v`
Expected: FAIL（`TypeError: 'vrc_updated_at' is an invalid keyword argument` 相当）

- [ ] **Step 3: db/models.py の World に3カラム追加**

`World` クラスの `ai_is_japanese` 行の直後に追記:

```python
    vrc_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    favorites: Mapped[int | None] = mapped_column(Integer)
    popularity: Mapped[int | None] = mapped_column(Integer)
```

- [ ] **Step 4: 実行して成功を確認**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add db/models.py tests/test_models.py
git commit -m "feat: WorldにVRChat指標カラム(更新日/お気に入り/人気)を追加"
```

---

## Task 2: init_db に Postgres カラム追加(ALTER)

**Files:**
- Modify: `db/engine.py`

**Interfaces:**
- Consumes: `engine`, `Base`。
- Produces: `init_db()` が Postgres 既存テーブルに不足カラムを冪等追加する。

> `create_all` は既存テーブルにカラムを追加しないため、本番(Postgres)の既存 `worlds` に手当てが必要。SQLite(テスト)は `create_all` が新カラム込みで作るので対象外。ユニットテストはSQLiteで `init_db()` が例外なく通ることだけ確認する。

- [ ] **Step 1: 失敗テストを書く** — `tests/test_engine_url.py` の末尾に追記

```python
async def test_init_db_runs_on_sqlite(monkeypatch, tmp_path):
    import db.engine as e
    from sqlalchemy.ext.asyncio import create_async_engine
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/t.db")
    monkeypatch.setattr(e, "engine", test_engine)
    await e.init_db()  # 例外が出なければOK
    await test_engine.dispose()
```

- [ ] **Step 2: 実行して失敗 or エラー確認**

Run: `python -m pytest tests/test_engine_url.py::test_init_db_runs_on_sqlite -v`
Expected: 現状の `init_db` は `e.engine` を直接参照するため PASS する可能性がある。PASS でも次へ（このテストは回帰防止用）。

- [ ] **Step 3: db/engine.py の init_db を更新**

冒頭の import に `text` を追加し、`init_db` を差し替え:

```python
from sqlalchemy import text
```

```python
async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == "postgresql":
            for col, ddl in (
                ("vrc_updated_at", "TIMESTAMP"),
                ("favorites", "INTEGER"),
                ("popularity", "INTEGER"),
            ):
                await conn.execute(text(f"ALTER TABLE worlds ADD COLUMN IF NOT EXISTS {col} {ddl}"))
```

- [ ] **Step 4: 実行して成功を確認**

Run: `python -m pytest tests/test_engine_url.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add db/engine.py tests/test_engine_url.py
git commit -m "feat: init_dbでPostgres既存テーブルに指標カラムを冪等追加"
```

---

## Task 3: 収集で指標を取得・保存

**Files:**
- Modify: `collector/vrc_client.py`（`_world_to_dict`）
- Modify: `db/repository.py`（`upsert_world`）
- Test: `tests/test_vrc_client.py`, `tests/test_repository.py`

**Interfaces:**
- Produces: `_world_to_dict` 戻り値に `vrc_updated_at` / `favorites` / `popularity` を含む。`upsert_world` がそれらを保存。

- [ ] **Step 1: 失敗テストを書く（_world_to_dict）** — `tests/test_vrc_client.py` の末尾に追記

```python
def test_world_to_dict_includes_metrics():
    from datetime import datetime
    import collector.vrc_client as vc

    class _W:
        id = "wrld_x"
        name = "name"
        author_name = "auth"
        description = "d"
        image_url = "http://img"
        capacity = 16
        tags = ["sleep"]
        updated_at = datetime(2026, 6, 2)
        favorites = 50
        popularity = 7

    d = vc._world_to_dict(_W())
    assert d["favorites"] == 50
    assert d["popularity"] == 7
    assert d["vrc_updated_at"].day == 2
```

- [ ] **Step 2: 実行して失敗を確認**

Run: `python -m pytest tests/test_vrc_client.py::test_world_to_dict_includes_metrics -v`
Expected: FAIL（KeyError: 'favorites'）

- [ ] **Step 3: collector/vrc_client.py の `_world_to_dict` に追記**

`return { ... }` の `"vrc_url": ...` 行の直後（dict内）に追加:

```python
        "vrc_updated_at": getattr(world, "updated_at", None),
        "favorites": getattr(world, "favorites", None),
        "popularity": getattr(world, "popularity", None),
```

- [ ] **Step 4: 失敗テストを書く（upsert_world）** — `tests/test_repository.py` の末尾に追記

```python
async def test_upsert_world_saves_metrics(session):
    from datetime import datetime
    from sqlalchemy import select
    from db.models import World
    from db.repository import upsert_world

    await upsert_world(session, {
        "world_id": "wrld_m", "name": "n", "author_name": "a",
        "vrc_url": "https://vrchat.com/home/world/wrld_m",
        "vrc_updated_at": datetime(2026, 6, 3), "favorites": 99, "popularity": 12,
    })
    row = (await session.execute(select(World).where(World.world_id == "wrld_m"))).scalar_one()
    assert row.favorites == 99
    assert row.popularity == 12
    assert row.vrc_updated_at.day == 3
```

- [ ] **Step 5: 実行して失敗を確認**

Run: `python -m pytest tests/test_repository.py::test_upsert_world_saves_metrics -v`
Expected: FAIL（保存されず None）

- [ ] **Step 6: db/repository.py の `upsert_world` に指標保存を追加**

`tags` を組み立てた後、更新ブランチ（既存world）に追記:

```python
        world.vrc_updated_at = data.get("vrc_updated_at")
        world.favorites = data.get("favorites")
        world.popularity = data.get("popularity")
```
（`world.fetched_at = datetime.utcnow()` の直前に置く）

新規作成ブランチの `World(...)` 引数に追加:

```python
        vrc_updated_at=data.get("vrc_updated_at"),
        favorites=data.get("favorites"),
        popularity=data.get("popularity"),
```
（`fetched_at=datetime.utcnow(),` と並べて追加）

- [ ] **Step 7: 実行して成功を確認**

Run: `python -m pytest tests/test_vrc_client.py tests/test_repository.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add collector/vrc_client.py db/repository.py tests/test_vrc_client.py tests/test_repository.py
git commit -m "feat: 収集時にVRChat指標(更新日/お気に入り/人気)を保存"
```

---

## Task 4: Tailwind CSS v4 導入

**Files:**
- Create: `postcss.config.mjs`
- Modify: `package.json`
- Modify: `app/globals.css`

**Interfaces:**
- Produces: Tailwind ユーティリティが使える。テーマ色トークン `bg`/`card`/`accent`/`ink`。

- [ ] **Step 1: package.json に devDependencies 追加**

`devDependencies` に追記（他は既存のまま）:

```json
    "tailwindcss": "^4.0.0",
    "@tailwindcss/postcss": "^4.0.0"
```

- [ ] **Step 2: postcss.config.mjs を作成**

```javascript
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
```

- [ ] **Step 3: app/globals.css を差し替え**

```css
@import "tailwindcss";

@theme {
  --color-bg: #0f0c1d;
  --color-card: #1a1530;
  --color-accent: #7b68ee;
  --color-ink: #e8e6f0;
}

body {
  background: var(--color-bg);
  color: var(--color-ink);
  font-family: system-ui, sans-serif;
}
```

- [ ] **Step 4: 依存インストールとビルド確認**

Run: `npm install && npm run build`
Expected: ビルド成功（Tailwind が PostCSS で処理される）

- [ ] **Step 5: Commit**

```bash
git add package.json package-lock.json postcss.config.mjs app/globals.css
git commit -m "feat: Tailwind CSS v4 を導入しテーマ色を定義"
```

---

## Task 5: lib/worlds.ts に指標・ピックアップ・並び替えを追加

**Files:**
- Modify: `lib/worlds.ts`

**Interfaces:**
- Produces:
  - 型 `World`（`favorites:number|null`, `popularity:number|null`, `vrc_updated_at:string|null` 追加）
  - `type SortKey = "updated" | "popularity" | "favorites"`
  - `getPickupWorlds(count=6, pool=100): Promise<World[]>`
  - `getWorlds(sort: SortKey, limit: number, offset: number): Promise<World[]>`
  - `parseTags(raw)`（既存）, `formatCount(n)`, `relativeTime(iso)`

- [ ] **Step 1: lib/worlds.ts を差し替え**

```typescript
import { sql } from "@/lib/db";

export type World = {
  world_id: string;
  name: string;
  author_name: string;
  description: string | null;
  image_url: string | null;
  tags: string | null;
  capacity: number | null;
  vrc_url: string;
  favorites: number | null;
  popularity: number | null;
  vrc_updated_at: string | null;
};

export type SortKey = "updated" | "popularity" | "favorites";

export async function getPickupWorlds(count = 6, pool = 100): Promise<World[]> {
  const { rows } = await sql<World>`
    SELECT * FROM (
      SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url,
             favorites, popularity, vrc_updated_at
      FROM worlds
      WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
      ORDER BY vrc_updated_at DESC NULLS LAST
      LIMIT ${pool}
    ) sub
    ORDER BY RANDOM()
    LIMIT ${count}
  `;
  return rows;
}

export async function getWorlds(sort: SortKey, limit: number, offset: number): Promise<World[]> {
  if (sort === "popularity") {
    const { rows } = await sql<World>`
      SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url,
             favorites, popularity, vrc_updated_at
      FROM worlds WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
      ORDER BY popularity DESC NULLS LAST LIMIT ${limit} OFFSET ${offset}`;
    return rows;
  }
  if (sort === "favorites") {
    const { rows } = await sql<World>`
      SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url,
             favorites, popularity, vrc_updated_at
      FROM worlds WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
      ORDER BY favorites DESC NULLS LAST LIMIT ${limit} OFFSET ${offset}`;
    return rows;
  }
  const { rows } = await sql<World>`
    SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url,
           favorites, popularity, vrc_updated_at
    FROM worlds WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
    ORDER BY vrc_updated_at DESC NULLS LAST LIMIT ${limit} OFFSET ${offset}`;
  return rows;
}

export function parseTags(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw) as string[];
    return arr.filter((t) => !t.startsWith("author_tag_")).slice(0, 6);
  } catch {
    return [];
  }
}

export function formatCount(n: number | null): string {
  if (n == null) return "-";
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const days = Math.floor((Date.now() - then) / 86400000);
  if (days <= 0) return "今日";
  if (days < 7) return `${days}日前`;
  if (days < 30) return `${Math.floor(days / 7)}週間前`;
  if (days < 365) return `${Math.floor(days / 30)}ヶ月前`;
  return `${Math.floor(days / 365)}年前`;
}
```

- [ ] **Step 2: 型チェック**

Run: `npm run typecheck`
Expected: 型エラーなし

- [ ] **Step 3: Commit**

```bash
git add lib/worlds.ts
git commit -m "feat: ピックアップ・並び替え・表示ヘルパをlib/worldsに追加"
```

---

## Task 6: Header / SortTabs / WorldCard コンポーネント

**Files:**
- Create: `components/Header.tsx`
- Create: `components/SortTabs.tsx`
- Modify: `components/WorldCard.tsx`

**Interfaces:**
- Consumes: 型 `World`, `parseTags`, `formatCount`, `relativeTime`, `SortKey`。

- [ ] **Step 1: components/Header.tsx を作成**

```tsx
export function Header() {
  return (
    <header className="sticky top-0 z-10 border-b border-[#2a2350] bg-bg/90 backdrop-blur">
      <div className="mx-auto max-w-5xl px-4 py-3">
        <a href="/" className="text-accent text-xl font-bold no-underline">🌙 ネドココ</a>
        <p className="mt-0.5 text-xs opacity-70">VRChatのぶい睡ワールドを見つける</p>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: components/SortTabs.tsx を作成**

```tsx
import type { SortKey } from "@/lib/worlds";

const TABS: { key: SortKey; label: string }[] = [
  { key: "updated", label: "新着" },
  { key: "popularity", label: "人気" },
  { key: "favorites", label: "お気に入り" },
];

export function SortTabs({ active }: { active: SortKey }) {
  return (
    <div className="flex gap-2">
      {TABS.map((t) => (
        <a
          key={t.key}
          href={`/?sort=${t.key}`}
          className={`rounded-full px-4 py-1.5 text-sm no-underline transition ${
            active === t.key ? "bg-accent text-white" : "bg-card text-ink/80 hover:text-ink"
          }`}
        >
          {t.label}
        </a>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: components/WorldCard.tsx を差し替え**

```tsx
import { formatCount, parseTags, relativeTime, type World } from "@/lib/worlds";

export function WorldCard({ world }: { world: World }) {
  const tags = parseTags(world.tags);
  return (
    <a
      href={world.vrc_url}
      target="_blank"
      rel="noreferrer"
      className="group block overflow-hidden rounded-xl border border-[#2a2350] bg-card no-underline text-ink transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/40"
    >
      {world.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={world.image_url}
          alt={world.name}
          loading="lazy"
          className="h-40 w-full object-cover"
        />
      )}
      <div className="p-3">
        <div className="truncate text-base font-bold">{world.name}</div>
        <div className="mt-0.5 truncate text-xs opacity-70">by {world.author_name}</div>
        {tags.length > 0 && (
          <div className="mt-2 truncate text-xs text-accent">
            {tags.map((t) => `#${t}`).join("　")}
          </div>
        )}
        <div className="mt-2 flex items-center gap-3 text-xs opacity-70">
          <span>❤ {formatCount(world.favorites)}</span>
          {world.capacity && <span>👥 {world.capacity}</span>}
          {world.vrc_updated_at && <span>🕒 {relativeTime(world.vrc_updated_at)}</span>}
        </div>
      </div>
    </a>
  );
}
```

- [ ] **Step 4: 型チェック**

Run: `npm run typecheck`
Expected: 型エラーなし

- [ ] **Step 5: Commit**

```bash
git add components/Header.tsx components/SortTabs.tsx components/WorldCard.tsx
git commit -m "feat: Header/SortTabs/WorldCard(Tailwind・指標表示)を追加"
```

---

## Task 7: 統合フィードページ & レイアウト & /worlds 廃止

**Files:**
- Modify: `app/page.tsx`
- Modify: `app/layout.tsx`
- Delete: `app/worlds/page.tsx`

**Interfaces:**
- Consumes: `getPickupWorlds`, `getWorlds`, `SortKey`, `Header`, `SortTabs`, `WorldCard`。

- [ ] **Step 1: app/layout.tsx のメタ情報を更新**

```tsx
import "./globals.css";

export const metadata = {
  title: "🌙 ネドココ",
  description:
    "AIがぶい睡（VR睡眠）に向いたVRChatワールドを厳選。新着・人気・お気に入りで探したり、ランダムで出会ったり。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 2: app/page.tsx を差し替え（統合フィード）**

```tsx
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
              <h2 className="text-lg font-bold text-accent">🎲 ランダムピックアップ</h2>
              <a href="/" className="text-sm opacity-70 hover:opacity-100">シャッフル ↻</a>
            </div>
            <div className={grid}>
              {pickup.map((w) => (
                <WorldCard key={`p-${w.world_id}`} world={w} />
              ))}
            </div>
          </section>
        )}

        <section>
          <div className="mb-3 flex items-center justify-between gap-3">
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

          <div className="mt-6 flex gap-4">
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
```

- [ ] **Step 3: app/worlds/page.tsx を削除**

Run:
```bash
git rm app/worlds/page.tsx
```
（空になった `app/worlds/` ディレクトリは git 管理外なので自然に消える）

- [ ] **Step 4: 型チェック＋ビルド**

Run: `npm run typecheck && npm run build`
Expected: 型エラーなし、ビルド成功、ルートに `/worlds` が無いこと

- [ ] **Step 5: Commit**

```bash
git add app/layout.tsx app/page.tsx
git commit -m "feat: 統合フィード(ピックアップ＋並び替え)化・メタ情報をネドココに・/worlds廃止"
```

---

## Task 8: 全テストと最終確認

**Files:** なし（検証）

- [ ] **Step 1: Python 全テスト**

Run: `python -m pytest -q`
Expected: 全 PASS

- [ ] **Step 2: Web 型チェック＋ビルド**

Run: `npm run typecheck && npm run build`
Expected: 型エラーなし・ビルド成功

- [ ] **Step 3: Commit（必要なら）**

```bash
git add -A
git commit -m "chore: UI見直しの最終確認"
```

---

## Self-Review（スペック突合）

- **データモデル拡張(updated/favorites/popularity)**: Task 1。✓
- **Postgres既存テーブルへのカラム追加**: Task 2（init_db ALTER）。✓
- **収集で指標保存**: Task 3（_world_to_dict + upsert_world）。✓
- **統合フィード・/worlds廃止・5件制限撤廃**: Task 7。✓
- **ランダムピックアップ(新着上位から)**: Task 5 `getPickupWorlds`（updated降順pool→RANDOM）+ Task 7 表示。✓
- **並び替え 新着/人気/お気に入り**: Task 5 `getWorlds` + Task 6 `SortTabs` + Task 7。✓
- **Tailwind/レスポンシブ/テーマ色**: Task 4・6・7（grid-cols レスポンシブ）。✓
- **サイト名ネドココ・キャッチ・meta説明**: Task 6 Header・Task 7 layout。✓
- **カードに指標表示(❤/🕒)**: Task 6。✓
- **get_random_worlds は残す**: 触れていない。✓
- 型整合: `World`(TS) 列、`SortKey`、関数シグネチャを各タスクで一致。プレースホルダ無し。✓
