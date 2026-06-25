# ネドココ UI 見直し 設計

作成日: 2026-06-25

## 概要

「ネドココ」（VRChatぶい睡ワールド推薦サイト）のUIを、レイアウト・構造とスマホ対応を中心に見直す。
「5件だけの提案」「今夜の提案と一覧の分離」を廃止し、**1つの統合フィード**に集約する。
並び替え（新着/人気/お気に入り）と、新着上位からのランダムピックアップを備える。

## 確定事項

| 項目 | 決定 |
|------|------|
| 重視点 | レイアウト・構造 / スマホ対応・使いやすさ |
| ページ構成 | `/` に統合（`/worlds` 廃止、5件制限・提案/一覧分離を廃止） |
| 上部 | 🎲 ランダムピックアップ枠（新着上位Nからランダム数件） |
| 下部 | メイン一覧（並び替え＋ページング） |
| 並び替え | 新着順(`vrc_updated_at`) / 人気順(`popularity`) / お気に入り順(`favorites`) |
| スタイル | Tailwind CSS |
| サイト名 | 🌙 ネドココ |
| キャッチ | 「VRChatのぶい睡ワールドを見つける」 |
| 説明(meta) | 「AIがぶい睡（VR睡眠）に向いたVRChatワールドを厳選。新着・人気・お気に入りで探したり、ランダムで出会ったり。」 |

対象ワールドは従来通り「ぶい睡適合（`ai_sleep_score >= 6` かつ `ai_is_japanese = 1`）」。

## データモデル拡張

VRChatの指標を保存していないため `World`（`db/models.py`）に3カラム追加（すべて nullable）:

| カラム | 型 | 由来（LimitedWorld/World 両方にある） |
|--------|----|--------------------------------------|
| `vrc_updated_at` | DateTime | `updated_at` |
| `favorites` | Integer | `favorites` |
| `popularity` | Integer | `popularity` |

- 収集時に `collector/vrc_client.py` の `_world_to_dict` で取得し、`db/repository.py` の `upsert_world` で保存（新規・更新の両方）。
- **既存ワールドのバックフィル**: 既存約679件は当初NULL。次回以降の収集で再出現したワールドから順次埋まる。NULLは並びで末尾（`NULLS LAST`）。
- スキーマ作成はPython側 `init_db()` の `create_all`。Postgresは新カラムを自動追加しない点に注意 → 既存テーブルへ `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` を `init_db()` で実行して追加する（後述）。

### マイグレーション方針

`create_all` は既存テーブルにカラムを追加しない。`db/engine.py` の `init_db()` で、`create_all` 後に冪等な `ALTER TABLE worlds ADD COLUMN IF NOT EXISTS ...`（Postgres）を実行して3カラムを足す。SQLite（テスト）では `create_all` が新カラム込みでテーブルを作るため不要だが、ALTERはSQLiteの `ADD COLUMN`（IF NOT EXISTSなし）も考慮し、Postgres時のみ実行する。

## リポジトリ（`db/repository.py`）

- `get_pickup_worlds(session, pool: int, count: int) -> list[World]`
  新着上位 `pool` 件（`vrc_updated_at` 降順、NULLS LAST）から `count` 件をランダム抽出。
- `list_qualified_worlds(session, sort: str, limit: int, offset: int) -> list[World]`
  `sort` は `"updated" | "popularity" | "favorites"`。それぞれ `vrc_updated_at` / `popularity` / `favorites` の降順（NULLS LAST）。既定 `"updated"`。
- 既存の `get_random_worlds` は Discord bot（`bot/cogs/suggest.py`）が参照しているため**残す**（Web側では使わない）。

## ページ構成（Next.js / `web/` → リポジトリ直下 `app/`）

- **`/`（統合フィード）** — Server Component、`force-dynamic`:
  1. ヘッダー（🌙 ネドココ ＋ キャッチ）。スマホでもコンパクト・固定。
  2. 🎲 ランダムピックアップ枠: `get_pickup_worlds(pool=100, count=6)`。リロードで変化。「シャッフル」リンク（`/` 再取得）。
  3. メイン一覧: 並び替えタブ（新着/人気/お気に入り、`?sort=` で保持）＋ページング（`?page=`、`?sort=` 維持）。`list_qualified_worlds`。
- **`/worlds` 廃止**（ファイル削除）。
- `lib/worlds.ts`: `getPickupWorlds()` と `getWorlds(sort, page)` を提供。SQLは `vrc_updated_at` / `popularity` / `favorites` でソート。

## カード表示（`components/WorldCard.tsx`）

- 既存: サムネ・ワールド名・作者・タグ（最大6、`author_tag_` 除外）・最大人数・「VRChatで開く」。
- 追加: お気に入り数（❤ 1.2k 形式で短縮）・更新日（🕒 相対表示「3日前」など）。人気度はお気に入り/更新で十分なら数値表示は最小限。
- ホバー/タップで軽い反応（影・わずかな拡大）。

## スタイル / レスポンシブ（Tailwind CSS）

- 導入: `tailwindcss` + `postcss` + `autoprefixer`、`tailwind.config.ts`、`postcss.config.mjs`、`globals.css` に `@tailwind base/components/utilities`。
- テーマ: 背景 `#0f0c1d`、カード `#1a1530`、アクセント midnight purple `#7B68EE`、文字 `#e8e6f0` を Tailwind theme.extend で定義。
- グリッド: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`（必要に応じ `xl:grid-cols-4`）。
- 画像: `loading="lazy"`、アスペクト比固定。
- タップ領域・余白をモバイル基準で確保。

## テスト方針

- **Python**:
  - `repository`: `get_pickup_worlds`（新着poolからcount件・しきい値遵守）、`list_qualified_worlds`（各sortの順序）。
  - `upsert_world`: 新カラム（updated_at/favorites/popularity）の保存。
  - `_world_to_dict`: 指標の取り出し（モックworldオブジェクト）。
- **Next.js**: `getWorlds`/`getPickupWorlds` のSQL（型・ソート）、ビルド/型チェック。E2Eは最小限。

## スコープ外（今回しない）

- サムネ画像のAI解析
- descriptionの追加採点（別途対応済み）
- 検索ボックス・タグ絞り込みUI
- ユーザー認証・お気に入り保存
