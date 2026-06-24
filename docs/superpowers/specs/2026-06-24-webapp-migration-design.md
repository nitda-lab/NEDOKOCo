# ぶい睡ワールド推薦 Webアプリ化 設計

作成日: 2026-06-24

## 概要

既存の Discord Bot「VRChat ぶい睡ワールド推薦」を Web アプリ化し、Vercel で公開する。
AI（ワールド採点）は OpenRouter から nanoGPT サブスクリプション（model=`gemma`）に切り替える。

Web アプリの主機能は **ワールド閲覧・提案**。チャット機能・検索フィルタ・Discord Bot 継続は今回のスコープ外。

## 確定事項（ブレインストーミングの結論）

| 項目 | 決定 |
|------|------|
| Web 機能 | ワールド閲覧・提案のみ（チャット/検索/Bot継続は対象外） |
| Collector 運用 | Vercel Cron に移植（分割実行） |
| Web スタック | Next.js (App Router, TypeScript) |
| DB | Neon (Postgres) |
| AI 用途 | ワールド採点のみ（nanoGPT, model=`gemma`） |
| 公開範囲 | 閲覧は公開 / 管理操作は要認証 |
| nanoGPT 接続 | OpenAI 互換 API, base_url=`https://nano-gpt.com/api/v1` |
| VRChat 認証 | `auth` + `twoFactorAuth` クッキーを DB 保存し OTP なし自動再ログイン |

## 全体アーキテクチャ

単一の Vercel プロジェクト内に、役割で分離した 2 言語を同居させる。

```
┌─────────────── Vercel (単一プロジェクト) ───────────────┐
│  Next.js (App Router, TypeScript)  ← 表示・読み取り       │
│   ├─ /          今夜のぶい睡ワールド（5件提案・再ロール）  │
│   ├─ /worlds    ぶい睡ワールド一覧（閲覧・ページング）     │
│   └─ /admin     管理画面（要認証）                         │
│        ↑ Server Component / @vercel/postgres で Neon read │
│                                                          │
│  Python Serverless Functions (/api/*.py)  ← 収集・採点    │
│   ├─ /api/cron/collect    Vercel Cron が定期起動          │
│   ├─ /api/admin/vrc-login VRChat ログイン開始             │
│   └─ /api/admin/vrc-otp   メール OTP 入力で認証完了        │
│        ↓ SQLAlchemy(asyncpg) で Neon read/write          │
└──────────────────────────────────────────────────────────┘
                          │
                    ┌─────▼─────┐
                    │ Neon (PG) │  worlds / app_state
                    └───────────┘
                          ▲
              nanoGPT API (採点: model=gemma)
```

- **言語は 2 つ**だが役割で完全分離。Next.js=表示・読み取り、Python=収集・採点・書き込み。同じ Neon DB を共有。
- 既存 Python ロジック（`vrc_client.py` / `ai_scorer.py` / `pipeline.py` / `repository.py`）は**ほぼ流用**。改修は次の 4 点に集約:
  1. OpenRouter → nanoGPT（base_url / api_key / model を env 化）
  2. SQLite → Postgres（接続文字列・型）
  3. ファイル保存 → `app_state` テーブル保存（クッキー・カーソル）
  4. 対話 OTP フロー → HTTP 2 ステップ化（プロセス内グローバル状態を DB 状態へ）
- **X collector (`x_collector.py`) は対象外**。現状 `pipeline.py` は VRChat 検索ベースで動作しており、`x_collector.py` は `repository.py` に存在しない関数（`add_world` 等）を参照する未使用/壊れたコード。VRChat 検索パイプラインに一本化する（X 連携は将来の別スペック）。

## データモデル（Neon Postgres）

### `worlds`

既存 `db/models.py` の `World` を Postgres 化。スキーマ変更なし（型を Postgres へ移植、`world_id` UNIQUE）。
`ai_is_japanese` は現状 Integer(1/0/NULL) を踏襲（既存クエリ互換のため Boolean へは変更しない）。

### `app_state`（新規）

サーバーレスはファイルが永続しないため、現在ファイルに置いている状態を KV テーブルに移す。

| key | 用途 |
|-----|------|
| `vrc_auth_cookie` | 認証済みクッキー（旧 `data/vrc_auth.cookie`） |
| `vrc_twofactor_cookie` | 2FA 通過証明クッキー（OTP なし再ログイン用、新規） |
| `vrc_pending_cookie` | OTP 待ちクッキー（旧 `data/vrc_pending.cookie`） |
| `collect_cursor` | 検索クエリ進捗インデックス（分割実行用） |
| `last_collect_at` | 最終収集時刻（管理画面表示用） |
| `last_status` | 最終結果（新規件数・採点件数・`auth_required` など） |

スキーマ作成は **Python 側が所有**。`init_db()` の `create_all` を cron 関数のコールドスタートで冪等実行する。Next.js 側は読むだけ（スキーマ定義を二重管理しない）。

## Collector 分割実行（時間制限対策）

Vercel のサーバーレス関数には実行時間上限（Hobby 60 秒 / Pro 5 分程度）がある。現状の「VRChat 検索 ~30 クエリ × 各 50 件 → AI 採点」を 1 回で全実行すると timeout する。
→ **単一エンドポイント `/api/cron/collect` ＋ カーソルで分割実行**する。

1 回の処理（すべて有界）:

1. `app_state` から認証クッキーを取得・検証。無効なら自動再ログインを試行（下記「VRChat 認証」）。それも不可なら `last_status="auth_required"` を書いて即終了。
2. `collect_cursor` の位置から **検索クエリを N 本だけ**（既定 4、env で調整可）実行 → `upsert_world`。カーソルを進め、末尾まで行ったら 0 に戻す（1 周）。
3. 続けて **未採点ワールドを 1 バッチだけ**（gemma 向けに `BATCH_SIZE`=20）nanoGPT で採点 → `save_ai_scores`。
4. `last_collect_at` / `last_status`（新規件数・採点件数）を更新。

- `vercel.json` の cron で数分間隔起動（例: `*/10 * * * *`）。全クエリ＋全採点を数回〜十数回に分けて消化。
- cron エンドポイントは Vercel が付与する `Authorization: Bearer $CRON_SECRET` で保護。
- 1 回あたりの上限（クエリ本数・採点バッチ数・`BATCH_SIZE`）は env で調整可能にする。

## VRChat 認証（OTP のサーバーレス対応）

VRChat のクッキーは 2 種類: `auth`（API 用、~数週間〜30 日）と `twoFactorAuth`（2FA 通過証明、~30 日）。
両方を `app_state` に保存することで、`auth` 失効時も OTP なしで自動再ログインでき、手動 OTP の頻度を最長で約 30 日に 1 回程度まで下げる。

### ログインフロー（HTTP 2 ステップ、管理画面から操作・要認証）

- `POST /api/admin/vrc-login` → `login()` を呼ぶ。
  - 保存済み `auth` が有効 → `"ok"`。
  - 無効/欠落 → ユーザー名＋パスワード＋保存済み `twoFactorAuth` クッキーで再ログイン試行。成功（OTP 不要）なら新しい `auth` を保存し `"ok"`。
  - VRChat が依然 2FA を要求（`twoFactorAuth` 欠落/失効）→ pending クッキーを `app_state` に保存し `"email_otp"`。
- `POST /api/admin/vrc-otp {code}` → `verify_email_otp()` で OTP 検証。成功時に **`auth` と `twoFactorAuth` の両方**をレスポンスヘッダから取得して `app_state` に保存。pending を削除。

### 改修点

- `vrc_client.py` のファイル I/O（`_load_file`/`_save_file`/`_delete_file`）を `app_state` 読み書きへ差し替え。
- プロセス内グローバル変数（`_pending_client` / `_pending_auth_cookie`）への依存を排し、**DB の pending クッキーから毎回クライアントを再構築**（サーバーレスはインスタンス使い捨てのため）。
- cron は `auth` 失効時にまず自動再ログインを試み、それも不可な場合のみ `auth_required` を立てる。

### 運用リスク

Vercel の実行元はデータセンター IP で毎回変わりうるため、VRChat 側が通常より早くセッションを無効化/警戒する可能性がある。その場合は再認証頻度が上がりうる。運用しながら様子見とする。

## AI / nanoGPT

`collector/ai_scorer.py` の改修のみ:

- `base_url = NANOGPT_BASE_URL`（既定 `https://nano-gpt.com/api/v1`）、`api_key = NANOGPT_API_KEY`、`model = SCORING_MODEL`（既定 `gemma`）。すべて env で差し替え可能。
- gemma は大量 JSON 出力が不安定になりやすいため `BATCH_SIZE` を 50 → 20 に縮小。
- 既存の「JSON 配列を `[`〜`]` で抽出・失敗バッチはスキップ」フォールバックを維持。採点失敗ワールドは未採点のまま次回再試行。

## フロントエンド（Next.js / App Router）

- **`/`（ホーム）**: 「🌙 今夜のぶい睡ワールド」。Server Component で `ai_sleep_score >= 6 AND ai_is_japanese = 1` からランダム 5 件を取得しカード表示。「別の 5 件を見る」ボタンで再ロール（Server Action + `revalidatePath`）。提案時に `last_suggested_at` / `suggest_count` を更新。
  - カード内容は既存 `build_world_embed` を踏襲: サムネ・ワールド名・作者・タグ（最大 6、`author_tag_` 接頭辞は除外）・最大人数・「VRChat で開く」リンク。
- **`/worlds`（一覧）**: 条件を満たす全ワールドを新着/人気順でページング表示。
- 共通: ねむねむテーマ（midnight purple `#7B68EE`）、レスポンシブなカードグリッド。
- **DB 読み取り**: `@vercel/postgres` のタグ付きテンプレート SQL（数クエリのみのため ORM を入れない）。スキーマ所有は Python、TS は読むだけ。

## 管理画面と認証

- **`/admin`**: 収集状況（`last_collect_at` / `last_status` / 未採点件数 / 総件数）、「今すぐ収集」ボタン（`/api/cron/collect` 手動キック）、VRChat ログイン＋ OTP 入力フォーム。
- **認証方式**: アプリレベルの共有シークレット。ログインフォームで `ADMIN_PASSWORD` を照合 → httpOnly 署名クッキーを発行。Next.js middleware で `/admin` ページと管理 API（`/api/admin/*`）を保護。管理 API の Python 関数側でも同じトークン/クッキーを検証（多層防御）。
- 閲覧系（`/`・`/worlds`）は認証なしで公開。

## エラー処理・運用

- **VRChat クッキー失効**: 自動再ログイン → 不可なら `auth_required` を記録、管理画面で赤表示＋再ログイン導線。
- **nanoGPT 採点失敗**: バッチ単位でスキップ（既存挙動）、未採点のまま次回再試行。
- **cron 時間制限**: 分割実行で構造的に回避。1 回あたり上限は env で調整。
- **`vercel.json`**: Python 関数の `maxDuration` をプラン上限内で引き上げ、cron スケジュール、ランタイム指定。

## 環境変数

| 変数 | 用途 |
|------|------|
| `DATABASE_URL` | Neon 接続文字列 |
| `NANOGPT_API_KEY` | nanoGPT API キー |
| `NANOGPT_BASE_URL` | 既定 `https://nano-gpt.com/api/v1` |
| `SCORING_MODEL` | 既定 `gemma` |
| `VRC_USERNAME` / `VRC_PASSWORD` | VRChat Bot アカウント |
| `CRON_SECRET` | Vercel Cron エンドポイント保護 |
| `ADMIN_PASSWORD` | 管理画面認証 |

（`X_BEARER_TOKEN` は今回未使用）

## テスト方針

TDD で各ユニットを実装する。

- **Python**:
  - `repository`: upsert / 採点保存 / ランダム取得（しきい値・除外時間）。
  - `ai_scorer`: JSON 抽出・失敗バッチのフォールバック。
  - `vrc_client`: クッキー DB 入出力、`auth` 失効時の自動再ログイン分岐、OTP 状態遷移（外部 API はモック）。
  - 収集の有界性: カーソルが N 本ずつ消化し末尾で 0 に戻る（1 周）。
- **Next.js**: ホームの提案ロジック（しきい値フィルタ＋ランダム件数）、管理認証ミドルウェア。E2E は最小限。

## スコープ外（将来の別スペック）

- サイト上のねむねむ bot チャット UI
- ワールド検索・フィルタ UI
- 推しコメント（AI 生成の紹介文）
- X（Twitter）連携によるワールド収集
- Discord Bot の継続運用
- ユーザー認証・個別レコメンド
