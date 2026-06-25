# ワールド作成（Launch）機能 設計

作成日: 2026-06-25

## 概要

ネドココの各ワールドから、VRChatのインスタンスを直接作成して入れる「Launch」機能を追加する。
訪問者自身のブラウザ/VRChatクライアントで作成する **Launchリンク方式**（認証不要・Bot不使用）。
インスタンスタイプを選択でき、region は日本(jp)固定。非Publicタイプは訪問者のVRChatユーザーID(usr_…)を使う。

## 確定事項

| 項目 | 決定 |
|------|------|
| 作成方式 | Launchリンク（`https://vrchat.com/home/launch?worldId=…&instanceId=…`）を生成して開く。Bot/サーバーAPI不使用 |
| region | jp 固定 |
| タイプ | public / friends_plus(hidden) / friends / invite_plus(private+canRequestInvite) / invite(private)。Group は対象外（グループID必須のため） |
| usr_ID | 非Publicに必要。localStorage `vrc_user_id` に保存。Public は不要 |
| 配置 | 各ワールドカードに「VRChatで建てる」ボタン＋ポップオーバー |

## 技術的背景（なぜこの方式か）

- 訪問者は当サイトでVRChat認証していない（認証済みはBotのみ）。Botで作るとBot所有になり非Public系は実質使えないため、**訪問者自身のクライアントで作る**Launchリンク方式を採用。
- 非Publicの instanceID には「作成者本人の usr_ID」を埋め込む必要があり、VRChatのログインCookieはクロスオリジンで読めない。よって**usr_IDを訪問者に一度入力してもらいlocalStorageに保存**する。nonce はVRChatクライアントが付与する。

## instanceID 生成（region=jp、name=乱数）

`buildInstanceId(type, usrId, name)`:

| type | instanceId |
|------|-----------|
| public | `<name>~region(jp)` |
| friends_plus | `<name>~hidden(<usr>)~region(jp)` |
| friends | `<name>~friends(<usr>)~region(jp)` |
| invite_plus | `<name>~private(<usr>)~canRequestInvite~region(jp)` |
| invite | `<name>~private(<usr>)~region(jp)` |

`buildLaunchUrl(worldId, instanceId)` → `https://vrchat.com/home/launch?worldId=<worldId>&instanceId=<encodeURIComponent(instanceId)>`

非Publicで `usrId` が空なら `buildInstanceId` は null を返す（呼び出し側で入力を促す）。

## コンポーネント構成（リポジトリ直下）

- `lib/launch.ts`（新規・純粋関数）
  - `export type InstanceType = "public" | "friends_plus" | "friends" | "invite_plus" | "invite"`
  - `randomInstanceName(): string`
  - `buildInstanceId(type: InstanceType, usrId: string | null, name: string): string | null`
  - `buildLaunchUrl(worldId: string, instanceId: string): string`
  - `needsUserId(type: InstanceType): boolean`（public 以外 true）
  - `isValidUserId(v: string): boolean`（`usr_` 始まり）
- `components/LaunchButton.tsx`（新規・`"use client"`）
  - props: `{ worldId: string }`
  - 「VRChatで建てる」ボタン＋ポップオーバー。タイプ選択肢を表示。
  - Public → 即 `buildInstanceId`/`buildLaunchUrl` → `window.open(url, "_blank")`。
  - 非Public → localStorage `vrc_user_id` を読み、未設定/不正なら入力欄を表示。`isValidUserId` を満たせば保存して生成・オープン。
  - 入力欄に「プロフィールURL `…/user/usr_xxxx` で確認」のヒント。
- `components/WorldCard.tsx`（変更）
  - ルートを `<a>` → `<div>`。画像＋タイトルを `<a href=vrc_url target=_blank>`（ワールドページ）に。
  - フッター: 指標（❤/👥/🕒）＋ `<LaunchButton worldId={world.world_id} />`。

## テスト方針

- `lib/launch.ts` は純粋関数。実装時に `node` で各タイプの instanceId/URL 文字列を出力確認（JSテストランナーは新規導入しない=YAGNI）。
- `npm run typecheck` / `npm run build` を通す。
- Python・DB・収集の変更なし。
- 実機確認: Public で新規JPインスタンス作成、非Public は usr_ID 設定後にVRChat起動（非Publicの nonce 挙動はクライアント任せ＝要実機確認）。

## スコープ外

- Group インスタンス（グループID必要）
- region 選択UI（jp固定）
- Bot/サーバーAPIによるインスタンス作成
- 作成済みインスタンスの一覧/人数表示
