# ワールド作成（Launch）機能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ネドココの各ワールドから、タイプ選択（region=jp固定）でVRChat Launchリンクを生成して開ける「建てる」機能を追加する。

**Architecture:** クライアント側のみ。純粋関数 `lib/launch.ts` がinstanceID/Launch URLを生成、`LaunchButton`(client) がタイプ選択とusr_ID(localStorage)を扱い `window.open`。`WorldCard` にボタンを内包。Bot/サーバー/DB変更なし。

**Tech Stack:** Next.js 15 (App Router, TS), Tailwind CSS v4。

## Global Constraints

- 作成方式: Launchリンクのみ（`https://vrchat.com/home/launch?worldId=…&instanceId=…`）。Bot/サーバーAPI不使用。
- region: `jp` 固定。
- タイプ: `public` / `friends_plus`(hidden) / `friends` / `invite_plus`(private+canRequestInvite) / `invite`(private)。Group対象外。
- 非Publicは usr_ID 必須、localStorage キー `vrc_user_id`、`usr_` 始まりを検証。Publicは不要。
- instanceID 形式（name=乱数）:
  - public `<name>~region(jp)`
  - friends_plus `<name>~hidden(<usr>)~region(jp)`
  - friends `<name>~friends(<usr>)~region(jp)`
  - invite_plus `<name>~private(<usr>)~canRequestInvite~region(jp)`
  - invite `<name>~private(<usr>)~region(jp)`

---

## File Structure

- `lib/launch.ts` (新規) — 純粋関数群。
- `components/LaunchButton.tsx` (新規, `"use client"`) — タイプ選択ポップオーバー＋usr_ID管理＋window.open。
- `components/WorldCard.tsx` (変更) — `<a>`ルート→`<div>`、画像/タイトルをリンクに、フッターにLaunchButton。

---

## Task 1: lib/launch.ts（純粋関数）

**Files:**
- Create: `lib/launch.ts`

**Interfaces:**
- Produces:
  - `type InstanceType = "public" | "friends_plus" | "friends" | "invite_plus" | "invite"`
  - `INSTANCE_TYPES: { key: InstanceType; label: string }[]`
  - `needsUserId(type: InstanceType): boolean`
  - `isValidUserId(v: string): boolean`
  - `randomInstanceName(): string`
  - `buildInstanceId(type: InstanceType, usrId: string | null, name: string): string | null`
  - `buildLaunchUrl(worldId: string, instanceId: string): string`

- [ ] **Step 1: lib/launch.ts を作成**

```typescript
export type InstanceType = "public" | "friends_plus" | "friends" | "invite_plus" | "invite";

export const INSTANCE_TYPES: { key: InstanceType; label: string }[] = [
  { key: "public", label: "Public" },
  { key: "friends_plus", label: "Friends+" },
  { key: "friends", label: "Friends" },
  { key: "invite_plus", label: "Invite+" },
  { key: "invite", label: "Invite" },
];

export function needsUserId(type: InstanceType): boolean {
  return type !== "public";
}

export function isValidUserId(v: string): boolean {
  return /^usr_[0-9a-f-]{8,}$/i.test(v.trim());
}

export function randomInstanceName(): string {
  return String(Math.floor(Math.random() * 90000) + 10000);
}

export function buildInstanceId(
  type: InstanceType,
  usrId: string | null,
  name: string,
): string | null {
  const region = "region(jp)";
  if (type === "public") return `${name}~${region}`;
  if (!usrId) return null;
  const u = usrId.trim();
  switch (type) {
    case "friends_plus":
      return `${name}~hidden(${u})~${region}`;
    case "friends":
      return `${name}~friends(${u})~${region}`;
    case "invite_plus":
      return `${name}~private(${u})~canRequestInvite~${region}`;
    case "invite":
      return `${name}~private(${u})~${region}`;
    default:
      return null;
  }
}

export function buildLaunchUrl(worldId: string, instanceId: string): string {
  return `https://vrchat.com/home/launch?worldId=${encodeURIComponent(worldId)}&instanceId=${encodeURIComponent(instanceId)}`;
}
```

- [ ] **Step 2: node で出力をサニティチェック**

Run:
```bash
node -e "const m=require('esbuild'); " 2>/dev/null || node --input-type=module -e "
import { buildInstanceId, buildLaunchUrl } from './lib/launch.ts';
" 2>/dev/null; echo 'note: ts直接実行不可なら手計算で確認'
```
代替（確実）: 次の式を手で確認する。
- `buildInstanceId('public', null, '12345')` → `12345~region(jp)`
- `buildInstanceId('friends', 'usr_abc', '12345')` → `12345~friends(usr_abc)~region(jp)`
- `buildInstanceId('invite_plus', 'usr_abc', '12345')` → `12345~private(usr_abc)~canRequestInvite~region(jp)`
- `buildInstanceId('friends', null, '12345')` → `null`
- `buildLaunchUrl('wrld_x', '12345~region(jp)')` → `https://vrchat.com/home/launch?worldId=wrld_x&instanceId=12345~region(jp)` のURLエンコード版

Expected: 上記と一致（実装と目視一致を確認）

- [ ] **Step 3: 型チェック**

Run: `npm run typecheck`
Expected: 型エラーなし

- [ ] **Step 4: Commit**

```bash
git add lib/launch.ts
git commit -m "feat: Launch URL/instanceID生成の純粋関数を追加"
```

---

## Task 2: LaunchButton コンポーネント

**Files:**
- Create: `components/LaunchButton.tsx`

**Interfaces:**
- Consumes: `lib/launch.ts`。
- Produces: `export function LaunchButton({ worldId }: { worldId: string })`。

- [ ] **Step 1: components/LaunchButton.tsx を作成**

```tsx
"use client";

import { useState } from "react";

import {
  buildInstanceId,
  buildLaunchUrl,
  INSTANCE_TYPES,
  isValidUserId,
  needsUserId,
  randomInstanceName,
  type InstanceType,
} from "@/lib/launch";

const STORAGE_KEY = "vrc_user_id";

export function LaunchButton({ worldId }: { worldId: string }) {
  const [open, setOpen] = useState(false);
  const [askId, setAskId] = useState(false);
  const [idInput, setIdInput] = useState("");
  const [pendingType, setPendingType] = useState<InstanceType | null>(null);
  const [error, setError] = useState("");

  function launch(type: InstanceType, usrId: string | null) {
    const id = buildInstanceId(type, usrId, randomInstanceName());
    if (!id) return;
    window.open(buildLaunchUrl(worldId, id), "_blank", "noopener");
    setOpen(false);
    setAskId(false);
    setPendingType(null);
    setError("");
  }

  function onPick(type: InstanceType) {
    if (!needsUserId(type)) {
      launch(type, null);
      return;
    }
    const saved = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    if (saved && isValidUserId(saved)) {
      launch(type, saved);
      return;
    }
    setPendingType(type);
    setAskId(true);
  }

  function saveIdAndLaunch() {
    if (!isValidUserId(idInput)) {
      setError("usr_ で始まるIDを入力してください");
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, idInput.trim());
    if (pendingType) launch(pendingType, idInput.trim());
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="rounded-md bg-accent px-3 py-1 text-xs font-bold text-white"
      >
        VRChatで建てる
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-1 w-56 rounded-lg border border-[#2a2350] bg-card p-3 shadow-xl">
          {!askId ? (
            <>
              <div className="mb-2 text-xs opacity-70">リージョン: 日本 (JP)</div>
              <div className="flex flex-col gap-1">
                {INSTANCE_TYPES.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => onPick(t.key)}
                    className="rounded px-2 py-1.5 text-left text-sm hover:bg-bg"
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="mb-1 text-xs">VRChatユーザーID (usr_…)</div>
              <div className="mb-2 text-[10px] opacity-60">
                プロフィールURL …/user/usr_xxxx で確認
              </div>
              <input
                value={idInput}
                onChange={(e) => setIdInput(e.target.value)}
                placeholder="usr_xxxxxxxx"
                className="mb-2 w-full rounded bg-bg px-2 py-1 text-sm outline-none"
              />
              {error && <div className="mb-2 text-[10px] text-red-400">{error}</div>}
              <button
                type="button"
                onClick={saveIdAndLaunch}
                className="w-full rounded bg-accent px-2 py-1 text-sm font-bold text-white"
              >
                保存して建てる
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 型チェック**

Run: `npm run typecheck`
Expected: 型エラーなし

- [ ] **Step 3: Commit**

```bash
git add components/LaunchButton.tsx
git commit -m "feat: LaunchButton(タイプ選択・usr_ID保存・window.open)を追加"
```

---

## Task 3: WorldCard を再構成して LaunchButton を内包

**Files:**
- Modify: `components/WorldCard.tsx`

**Interfaces:**
- Consumes: `LaunchButton`, `formatCount`, `parseTags`, `relativeTime`, `World`。

- [ ] **Step 1: components/WorldCard.tsx を差し替え**

```tsx
import { LaunchButton } from "@/components/LaunchButton";
import { formatCount, parseTags, relativeTime, type World } from "@/lib/worlds";

export function WorldCard({ world }: { world: World }) {
  const tags = parseTags(world.tags);
  return (
    <div className="overflow-hidden rounded-xl border border-[#2a2350] bg-card text-ink transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/40">
      <a href={world.vrc_url} target="_blank" rel="noreferrer" className="block no-underline text-ink">
        {world.image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={world.image_url}
            alt={world.name}
            loading="lazy"
            className="h-40 w-full object-cover"
          />
        )}
        <div className="px-3 pt-3">
          <div className="truncate text-base font-bold">{world.name}</div>
          <div className="mt-0.5 truncate text-xs opacity-70">by {world.author_name}</div>
          {tags.length > 0 && (
            <div className="mt-2 truncate text-xs text-accent">
              {tags.map((t) => `#${t}`).join("　")}
            </div>
          )}
        </div>
      </a>
      <div className="flex items-center justify-between gap-2 px-3 pb-3 pt-2">
        <div className="flex items-center gap-3 text-xs opacity-70">
          <span>❤ {formatCount(world.favorites)}</span>
          {world.capacity && <span>👥 {world.capacity}</span>}
          {world.vrc_updated_at && <span>🕒 {relativeTime(world.vrc_updated_at)}</span>}
        </div>
        <LaunchButton worldId={world.world_id} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 型チェック＋ビルド**

Run: `npm run typecheck && npm run build`
Expected: 型エラーなし・ビルド成功

- [ ] **Step 3: Commit**

```bash
git add components/WorldCard.tsx
git commit -m "feat: WorldCardにLaunchButtonを内包・カード構造を調整"
```

---

## Task 4: 最終確認

**Files:** なし

- [ ] **Step 1: 型チェック＋ビルド＋Pythonテスト（回帰確認）**

Run: `npm run typecheck && npm run build && python -m pytest -q`
Expected: すべて成功

- [ ] **Step 2: 最終コミット（必要なら）**

```bash
git add -A
git commit -m "chore: Launch機能の最終確認"
```

---

## Self-Review（スペック突合）

- **Launchリンク方式・Bot不使用**: Task 1（純粋関数）+ Task 2（window.open）。✓
- **region jp 固定**: `buildInstanceId` に `region(jp)` 固定。✓
- **タイプ5種・Group除外**: `INSTANCE_TYPES`・`buildInstanceId`。✓
- **usr_ID localStorage `vrc_user_id`・`usr_`検証・Public不要**: Task 2（`needsUserId`/`isValidUserId`/STORAGE_KEY）。✓
- **instanceID 各形式**: Global Constraints と `buildInstanceId` 一致。✓
- **カードにボタン内包・ルート構造変更**: Task 3。✓
- **Python/DB/収集 変更なし**: 対象タスクなし。✓
- 型整合: `InstanceType`、関数シグネチャ、props を各タスクで一致。プレースホルダ無し。✓
