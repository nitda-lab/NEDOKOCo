# ぶい睡ワールド推薦 Webアプリ化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 既存の VRChat ぶい睡ワールド推薦 Discord Bot を、Vercel 上で動く Web アプリ（Next.js 表示 + Python 収集/採点）へ移行する。

**Architecture:** 単一 Vercel プロジェクトに 2 言語を役割分離で同居。Next.js(App Router/TS) が Neon Postgres を読み取って閲覧・提案 UI を提供。Python サーバーレス関数が VRChat 検索・nanoGPT 採点を行い同じ DB に書き込む。収集は Vercel Cron がカーソルで分割実行し関数時間制限を回避。

**Tech Stack:** Next.js 15 (App Router, TypeScript), @vercel/postgres, Python 3.11+ (Vercel `@vercel/python`), SQLAlchemy 2.0 + asyncpg, OpenAI SDK (nanoGPT 互換), vrchatapi, pytest.

## Global Constraints

- DB 操作は必ず `db/repository.py` 経由。cog/関数から model を直接触らない（既存方針）。
- コメントは原則書かない。書くなら「なぜ」が自明でない箇所のみ（既存方針）。
- 不要な抽象化・将来用の設計をしない（YAGNI）。OWASP Top 10 等の脆弱性を入れない。
- Python ユニットテストはインメモリ SQLite（`sqlite+aiosqlite:///:memory:`）で実行。本番は `DATABASE_URL`(Neon Postgres) を env で注入。
- 同期ライブラリ（vrchatapi）は `asyncio.to_thread()` でラップ（既存方針）。
- nanoGPT: base_url 既定 `https://nano-gpt.com/api/v1`、model 既定 `gemma`、すべて env 差し替え可能。
- 採点 `BATCH_SIZE` 既定 20。収集 1 回あたりの検索クエリ本数 `COLLECT_QUERY_BATCH` 既定 4。
- ぶい睡しきい値: `ai_sleep_score >= 6 AND ai_is_japanese = 1`。
- テーマ色 midnight purple `#7B68EE`。
- 既存 `x_collector.py`・Discord Bot 関連（`bot/`・`main.py`）は本移行では変更も削除もしない（スコープ外、放置）。

---

## File Structure

新規/変更ファイルと責務:

- `requirements.txt` (変更) — `asyncpg` 追加、`pytest`/`pytest-asyncio` を追加（dev も同居）。
- `db/models.py` (変更) — `AppState` モデル追加。`World` はそのまま（Postgres 互換）。
- `db/engine.py` (変更) — Postgres/SQLite 両対応、既定値整理。
- `db/state.py` (新規) — `app_state` の KV read/write ヘルパ。
- `db/repository.py` (変更) — 収集カーソル・統計用の関数追加。
- `collector/ai_scorer.py` (変更) — nanoGPT 化、`BATCH_SIZE` 既定 20、env 化。
- `collector/vrc_client.py` (変更) — クッキー保存先を `app_state` に、`twoFactorAuth` 保存と自動再ログイン、OTP 2 ステップ化。
- `collector/pipeline.py` (変更) — カーソルで有界実行する `run_collection_chunk()`。
- `api/_shared.py` (新規) — Python 関数共通: env ロード・DB 初期化・認証ヘルパ・JSON レスポンス。
- `api/cron/collect.py` (新規) — Cron エンドポイント（`run_collection_chunk` を呼ぶ）。
- `api/admin/vrc_login.py` (新規) — VRChat ログイン開始。
- `api/admin/vrc_otp.py` (新規) — メール OTP 検証。
- `tests/` (新規) — pytest。`conftest.py` + 各ユニットテスト。
- `web/` (新規) — Next.js アプリ（後述）。Vercel のルートを `web/` に設定。
  - `web/package.json`, `web/tsconfig.json`, `web/next.config.ts`
  - `web/lib/db.ts` — Neon 読み取り（`@vercel/postgres`）。
  - `web/lib/worlds.ts` — 提案/一覧クエリ。
  - `web/lib/auth.ts` — 管理認証（署名クッキー）。
  - `web/middleware.ts` — `/admin` 保護。
  - `web/app/page.tsx` — ホーム（提案 5 件 + 再ロール）。
  - `web/app/worlds/page.tsx` — 一覧。
  - `web/app/admin/page.tsx` + `web/app/admin/login/page.tsx` — 管理 UI。
  - `web/app/api/admin/login/route.ts` — 管理ログイン。
  - `web/components/WorldCard.tsx` — カード。
- `vercel.json` (新規) — cron・関数 runtime/maxDuration・ルート設定。
- `.env.example` (変更) — 新 env 追記。

> 注: Python 関数を `api/` 直下、Next.js を `web/` 配下に分けることで、Next.js の `app/api` と Vercel の Python Functions のルート衝突を避ける。`vercel.json` で両者を結線する（Task 14）。

---

## Phase 0: セットアップ

### Task 1: 依存とテスト基盤

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`, `tests/conftest.py`, `pytest.ini`

**Interfaces:**
- Produces: pytest fixture `session` (`AsyncSession`, インメモリ SQLite, 全テーブル作成済み)。

- [ ] **Step 1: requirements.txt に追記**

`requirements.txt` を次の内容にする（既存行は残し、末尾に追加）:

```
py-cord==2.8.0
aiosqlite==0.22.0
sqlalchemy[asyncio]==2.0.41
tweepy==4.15.0
vrchatapi==1.20.1
python-dotenv==1.1.0
openai>=1.0.0
asyncpg==0.30.0
pytest==8.3.4
pytest-asyncio==0.25.2
```

- [ ] **Step 2: pytest.ini を作成**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 3: tests/conftest.py を作成**

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models import Base


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()
```

- [ ] **Step 4: tests/__init__.py を作成（空ファイル）**

- [ ] **Step 5: 依存をインストール**

Run: `pip install -r requirements.txt`
Expected: 成功（asyncpg/pytest 等が入る）

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini tests/__init__.py tests/conftest.py
git commit -m "chore: pytest基盤とasyncpg依存を追加"
```

---

## Phase 1: データモデルと状態ストア

### Task 2: AppState モデル

**Files:**
- Modify: `db/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `AppState(key: str PK, value: str|None)` ORM モデル。

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_models.py`

```python
from db.models import AppState


async def test_app_state_insert_and_read(session):
    session.add(AppState(key="foo", value="bar"))
    await session.commit()

    from sqlalchemy import select
    result = await session.execute(select(AppState).where(AppState.key == "foo"))
    row = result.scalar_one()
    assert row.value == "bar"
```

- [ ] **Step 2: 実行して失敗を確認**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL（`ImportError: cannot import name 'AppState'`）

- [ ] **Step 3: db/models.py に AppState を追加**

`db/models.py` の末尾に追記:

```python
class AppState(Base):
    __tablename__ = "app_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(String)
```

- [ ] **Step 4: 実行して成功を確認**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add db/models.py tests/test_models.py
git commit -m "feat: app_state用 AppState モデルを追加"
```

### Task 3: app_state KV ヘルパ

**Files:**
- Create: `db/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces:
  - `async def get_state(session, key: str) -> str | None`
  - `async def set_state(session, key: str, value: str | None) -> None`（upsert、commit する）
  - `async def delete_state(session, key: str) -> None`（commit する）
  - 定数: `VRC_AUTH_COOKIE="vrc_auth_cookie"`, `VRC_TWOFACTOR_COOKIE="vrc_twofactor_cookie"`, `VRC_PENDING_COOKIE="vrc_pending_cookie"`, `COLLECT_CURSOR="collect_cursor"`, `LAST_COLLECT_AT="last_collect_at"`, `LAST_STATUS="last_status"`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_state.py`

```python
from db.state import delete_state, get_state, set_state


async def test_set_get_roundtrip(session):
    assert await get_state(session, "k") is None
    await set_state(session, "k", "v1")
    assert await get_state(session, "k") == "v1"


async def test_set_upsert_overwrites(session):
    await set_state(session, "k", "v1")
    await set_state(session, "k", "v2")
    assert await get_state(session, "k") == "v2"


async def test_delete(session):
    await set_state(session, "k", "v")
    await delete_state(session, "k")
    assert await get_state(session, "k") is None
```

- [ ] **Step 2: 実行して失敗を確認**

Run: `python -m pytest tests/test_state.py -v`
Expected: FAIL（`ModuleNotFoundError: db.state`）

- [ ] **Step 3: db/state.py を作成**

```python
from sqlalchemy import select

from db.models import AppState

VRC_AUTH_COOKIE = "vrc_auth_cookie"
VRC_TWOFACTOR_COOKIE = "vrc_twofactor_cookie"
VRC_PENDING_COOKIE = "vrc_pending_cookie"
COLLECT_CURSOR = "collect_cursor"
LAST_COLLECT_AT = "last_collect_at"
LAST_STATUS = "last_status"


async def get_state(session, key: str) -> str | None:
    result = await session.execute(select(AppState).where(AppState.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else None


async def set_state(session, key: str, value: str | None) -> None:
    result = await session.execute(select(AppState).where(AppState.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(AppState(key=key, value=value))
    await session.commit()


async def delete_state(session, key: str) -> None:
    result = await session.execute(select(AppState).where(AppState.key == key))
    row = result.scalar_one_or_none()
    if row:
        await session.delete(row)
        await session.commit()
```

- [ ] **Step 4: 実行して成功を確認**

Run: `python -m pytest tests/test_state.py -v`
Expected: PASS（3 件）

- [ ] **Step 5: Commit**

```bash
git add db/state.py tests/test_state.py
git commit -m "feat: app_state KVヘルパ(get/set/delete)を追加"
```

### Task 4: engine の Postgres 対応整理

**Files:**
- Modify: `db/engine.py`

**Interfaces:**
- Produces: `DATABASE_URL` を env から取得（既定 `sqlite+aiosqlite:///data/buisui.db`）。Postgres URL（`postgres://`/`postgresql://`）を渡された場合は `postgresql+asyncpg://` へ正規化する `_normalize_url(raw)`。`engine`, `AsyncSessionLocal`, `init_db()` は既存名のまま維持。
- Test: `tests/test_engine_url.py`

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_engine_url.py`

```python
from db.engine import _normalize_url


def test_normalize_postgres_scheme():
    assert _normalize_url("postgres://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"


def test_normalize_postgresql_scheme():
    assert _normalize_url("postgresql://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"


def test_normalize_strips_sslmode_query_for_asyncpg():
    # asyncpg は sslmode クエリを解さないため除去される
    out = _normalize_url("postgresql://u:p@h/db?sslmode=require")
    assert "sslmode" not in out
    assert out.startswith("postgresql+asyncpg://")


def test_normalize_passthrough_sqlite():
    assert _normalize_url("sqlite+aiosqlite:///x.db") == "sqlite+aiosqlite:///x.db"
```

- [ ] **Step 2: 実行して失敗を確認**

Run: `python -m pytest tests/test_engine_url.py -v`
Expected: FAIL（`_normalize_url` 未定義）

- [ ] **Step 3: db/engine.py を更新**

```python
import os
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.models import Base


def _normalize_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://"):]
    if raw.startswith("postgresql+asyncpg://"):
        parts = urlsplit(raw)
        # asyncpg は sslmode/channel_binding 等の libpq クエリを解さないため除去
        if parts.query:
            raw = urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment))
    return raw


DATABASE_URL = _normalize_url(os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/buisui.db"))

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

- [ ] **Step 4: 実行して成功を確認**

Run: `python -m pytest tests/test_engine_url.py -v`
Expected: PASS（4 件）

- [ ] **Step 5: Commit**

```bash
git add db/engine.py tests/test_engine_url.py
git commit -m "feat: DATABASE_URLのPostgres(asyncpg)正規化に対応"
```

### Task 5: repository に統計関数を追加

**Files:**
- Modify: `db/repository.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Consumes: `upsert_world`, `save_ai_scores`, `get_random_worlds`, `get_unscored_worlds`（既存）。
- Produces:
  - `async def count_worlds(session) -> int`（総件数）
  - `async def count_unscored(session) -> int`（`ai_sleep_score IS NULL` 件数）
  - `async def count_qualified(session) -> int`（しきい値を満たす件数）
  - `async def list_qualified_worlds(session, limit: int, offset: int) -> list[World]`（新着順、一覧用）

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_repository.py`

```python
from db.repository import (
    count_qualified,
    count_unscored,
    count_worlds,
    get_random_worlds,
    list_qualified_worlds,
    save_ai_scores,
    upsert_world,
)


def _world(i: int) -> dict:
    return {
        "world_id": f"wrld_{i}",
        "name": f"world {i}",
        "author_name": "author",
        "vrc_url": f"https://vrchat.com/home/world/wrld_{i}",
    }


async def test_counts_and_qualified_listing(session):
    for i in range(3):
        await upsert_world(session, _world(i))
    assert await count_worlds(session) == 3
    assert await count_unscored(session) == 3
    assert await count_qualified(session) == 0

    await save_ai_scores(session, [
        {"world_id": "wrld_0", "is_japanese": True, "sleep_score": 8},
        {"world_id": "wrld_1", "is_japanese": True, "sleep_score": 3},
        {"world_id": "wrld_2", "is_japanese": False, "sleep_score": 9},
    ])
    assert await count_unscored(session) == 0
    assert await count_qualified(session) == 1

    qualified = await list_qualified_worlds(session, limit=10, offset=0)
    assert [w.world_id for w in qualified] == ["wrld_0"]


async def test_get_random_worlds_respects_threshold(session):
    await upsert_world(session, _world(0))
    await save_ai_scores(session, [{"world_id": "wrld_0", "is_japanese": True, "sleep_score": 8}])
    worlds = await get_random_worlds(session, count=5)
    assert len(worlds) == 1
```

- [ ] **Step 2: 実行して失敗を確認**

Run: `python -m pytest tests/test_repository.py -v`
Expected: FAIL（`count_worlds` 等が未定義）

- [ ] **Step 3: db/repository.py に追記**

ファイル末尾に追加:

```python
async def count_worlds(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(World))
    return int(result.scalar_one())


async def count_unscored(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count()).select_from(World).where(World.ai_sleep_score == None)  # noqa: E711
    )
    return int(result.scalar_one())


async def count_qualified(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(World)
        .where(World.ai_sleep_score >= _SUGGEST_SCORE_MIN)
        .where(World.ai_is_japanese == 1)
    )
    return int(result.scalar_one())


async def list_qualified_worlds(session: AsyncSession, limit: int, offset: int) -> list[World]:
    stmt = (
        select(World)
        .where(World.ai_sleep_score >= _SUGGEST_SCORE_MIN)
        .where(World.ai_is_japanese == 1)
        .order_by(World.fetched_at.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
```

- [ ] **Step 4: 実行して成功を確認**

Run: `python -m pytest tests/test_repository.py -v`
Expected: PASS（2 件）

- [ ] **Step 5: Commit**

```bash
git add db/repository.py tests/test_repository.py
git commit -m "feat: 件数集計と一覧取得のrepository関数を追加"
```

---

## Phase 2: nanoGPT 採点

### Task 6: ai_scorer を nanoGPT 化

**Files:**
- Modify: `collector/ai_scorer.py`
- Test: `tests/test_ai_scorer.py`

**Interfaces:**
- Consumes: env `NANOGPT_API_KEY`, `NANOGPT_BASE_URL`, `SCORING_MODEL`。
- Produces: `score_worlds(worlds: list[dict]) -> list[dict]`（シグネチャ不変）。内部 `_extract_json_array(raw: str) -> list[dict]` を公開し単体テスト可能にする。`BATCH_SIZE=20`。

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_ai_scorer.py`

```python
from collector.ai_scorer import _build_world_summary, _extract_json_array


def test_extract_json_array_with_surrounding_text():
    raw = ' here you go: [{"world_id":"a","is_japanese":true,"sleep_score":8}] done'
    out = _extract_json_array(raw)
    assert out == [{"world_id": "a", "is_japanese": True, "sleep_score": 8}]


def test_extract_json_array_invalid_returns_empty():
    assert _extract_json_array("no json here") == []
    assert _extract_json_array("[broken") == []


def test_build_world_summary_filters_system_tags():
    s = _build_world_summary({
        "world_id": "a", "name": "n", "author_name": "x",
        "tags": '["system_approved", "chill"]',
    })
    assert s["tags"] == ["chill"]
```

- [ ] **Step 2: 実行して失敗を確認**

Run: `python -m pytest tests/test_ai_scorer.py -v`
Expected: FAIL（`_extract_json_array` 未定義）

- [ ] **Step 3: collector/ai_scorer.py を更新**

先頭の定数とクライアント生成を差し替え、JSON 抽出を関数化:

```python
import json
import os

from openai import OpenAI

NANOGPT_API_KEY = os.getenv("NANOGPT_API_KEY", "")
NANOGPT_BASE_URL = os.getenv("NANOGPT_BASE_URL", "https://nano-gpt.com/api/v1")
MODEL = os.getenv("SCORING_MODEL", "gemma")
BATCH_SIZE = int(os.getenv("SCORING_BATCH_SIZE", "20"))

PROMPT_TEMPLATE = """\
あなたはVRChatのワールドキュレーターです。
以下のワールドリストを評価し、必ずJSON配列のみを返してください（説明文不要）。

評価項目:
- is_japanese: 日本/アジア圏ユーザー向けワールドかどうか（bool）
  作者名やワールド名に日本語文字があれば true。英語名でも日本語コミュニティ向けなら true。
- sleep_score: ぶい睡（VRChat内で眠ること）に適した空間かのスコア（整数 1〜10）
  高スコア基準: 静か・ambient・chill・ベッドあり・night系・落ち着き・和み・星・月・夜
  低スコア基準: アクション・ゲーム・賑やか・パーティ・戦闘・スポーツ

返答形式（このJSONのみ、余分なテキスト禁止）:
[{{"world_id":"...","is_japanese":true,"sleep_score":8}}, ...]

ワールドリスト:
{worlds_json}"""


def _build_world_summary(world: dict) -> dict:
    tags_raw = world.get("tags") or "[]"
    try:
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
        tags = [t for t in tags if not t.startswith("system_")]
    except Exception:
        tags = []
    return {
        "world_id": world["world_id"],
        "name": world["name"],
        "author": world.get("author_name", ""),
        "tags": tags[:10],
    }


def _extract_json_array(raw: str) -> list[dict]:
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start == -1 or end == 0:
        return []
    try:
        parsed = json.loads(raw[start:end])
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def score_worlds(worlds: list[dict]) -> list[dict]:
    """nanoGPT経由でワールドを一括評価。失敗バッチはスキップ。"""
    if not NANOGPT_API_KEY:
        raise RuntimeError("NANOGPT_API_KEY が設定されていません")

    client = OpenAI(api_key=NANOGPT_API_KEY, base_url=NANOGPT_BASE_URL)
    results: list[dict] = []

    for i in range(0, len(worlds), BATCH_SIZE):
        batch = worlds[i: i + BATCH_SIZE]
        summaries = [_build_world_summary(w) for w in batch]
        worlds_json = json.dumps(summaries, ensure_ascii=False, indent=None)
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(worlds_json=worlds_json)}],
            )
            results.extend(_extract_json_array(response.choices[0].message.content.strip()))
        except Exception:
            continue

    return results
```

- [ ] **Step 4: 実行して成功を確認**

Run: `python -m pytest tests/test_ai_scorer.py -v`
Expected: PASS（3 件）

- [ ] **Step 5: Commit**

```bash
git add collector/ai_scorer.py tests/test_ai_scorer.py
git commit -m "feat: 採点をnanoGPT(gemma)に切替・JSON抽出を関数化"
```

---

## Phase 3: VRChat 認証のサーバーレス対応

### Task 7: vrc_client のクッキー DB 化と自動再ログイン

**Files:**
- Modify: `collector/vrc_client.py`
- Test: `tests/test_vrc_client.py`

**Interfaces:**
- Consumes: `db.state`（クッキー保存）, `db.engine.AsyncSessionLocal`。
- Produces（async 化。プロセス内グローバル状態を廃し DB を真実とする）:
  - `async def login() -> str` — 戻り値 `"ok" | "email_otp"`。
  - `async def verify_email_otp(code: str) -> None`。
  - `def search_worlds() -> list[dict]`（同期のまま、`asyncio.to_thread` で呼ぶ。内部はクッキー文字列を引数で受ける `_search_worlds_with_cookie(cookie: str)` に委譲）。
  - `async def get_active_cookie() -> str | None` — 有効な `auth` クッキーを返す（無ければ自動再ログイン試行、最終的に無ければ None）。
  - 純粋関数 `_extract_auth_cookie(headers) -> str | None`、`_extract_twofactor_cookie(headers) -> str | None`。

> ログインの細かな VRChat 呼び出し（Basic 認証ヘッダ生成・`get_current_user`・OTP 検証）は同期 vrchatapi なので、内部同期関数を `asyncio.to_thread` で実行し、結果のクッキー保存だけを async で `app_state` に書く構成にする。

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_vrc_client.py`

純粋なクッキー抽出関数と、状態遷移（OTP 要求時に pending を保存）をモックで検証する。

```python
import collector.vrc_client as vc
from db.state import VRC_AUTH_COOKIE, VRC_PENDING_COOKIE, get_state, set_state


def test_extract_auth_cookie():
    headers = {"Set-Cookie": "auth=authcookie_abc; Path=/; HttpOnly"}
    assert vc._extract_auth_cookie(headers) == "authcookie_abc"
    assert vc._extract_auth_cookie({}) is None


def test_extract_twofactor_cookie():
    headers = {"Set-Cookie": "twoFactorAuth=tfa_xyz; Path=/"}
    assert vc._extract_twofactor_cookie(headers) == "tfa_xyz"
    assert vc._extract_twofactor_cookie({}) is None


async def test_login_saved_cookie_valid_returns_ok(session, monkeypatch):
    await set_state(session, VRC_AUTH_COOKIE, "authcookie_saved")

    # AsyncSessionLocal を test session に差し替え
    monkeypatch.setattr(vc, "_session", lambda: _ctx(session))
    # 保存済みクッキー検証を成功させる
    monkeypatch.setattr(vc, "_verify_cookie_sync", lambda cookie: True)

    assert await vc.login() == "ok"


async def test_login_requires_otp_saves_pending(session, monkeypatch):
    monkeypatch.setattr(vc, "_session", lambda: _ctx(session))
    monkeypatch.setattr(vc, "_verify_cookie_sync", lambda cookie: False)
    # 新規ログインは email_otp を要求し pending クッキーを返す
    monkeypatch.setattr(vc, "_password_login_sync", lambda tfa: ("email_otp", "authcookie_pending", None))

    assert await vc.login() == "email_otp"
    assert await get_state(session, VRC_PENDING_COOKIE) == "authcookie_pending"


class _ctx:
    def __init__(self, s): self._s = s
    async def __aenter__(self): return self._s
    async def __aexit__(self, *a): return False
```

> 実装は `vc._session()` を「`AsyncSessionLocal()` を返す callable」として用意し、テストで差し替え可能にする。`_verify_cookie_sync(cookie)`・`_password_login_sync(twofactor_cookie)` の 2 つの同期関数に VRChat I/O を閉じ込め、テストはそこをモックする。

- [ ] **Step 2: 実行して失敗を確認**

Run: `python -m pytest tests/test_vrc_client.py -v`
Expected: FAIL（新関数群が未定義）

- [ ] **Step 3: collector/vrc_client.py を更新**

ファイル全体を次の構成に再実装（検索クエリ定数 `SEARCH_QUERIES`・`_q`・`_world_to_dict`・`get_world` は既存を維持）:

```python
import asyncio
import base64
import os
import re
from urllib.parse import quote

import vrchatapi
from vrchatapi.api import AuthenticationApi, WorldsApi
from vrchatapi.exceptions import ApiException
from vrchatapi.models import TwoFactorEmailCode

from db.engine import AsyncSessionLocal
from db.state import (
    VRC_AUTH_COOKIE,
    VRC_PENDING_COOKIE,
    VRC_TWOFACTOR_COOKIE,
    delete_state,
    get_state,
    set_state,
)

VRC_USERNAME = os.getenv("VRC_USERNAME", "")
VRC_PASSWORD = os.getenv("VRC_PASSWORD", "")
USER_AGENT = "buisui-bot/1.0 smileglass314@gmail.com"


def _q(text: str) -> str:
    return quote(text, safe="", encoding="utf-8")


SEARCH_QUERIES: list[dict] = [
    {"search": _q("ぶい睡")}, {"search": _q("ぶいすい")}, {"search": "buisui"},
    {"search": _q("VR睡眠")}, {"search": _q("睡眠")}, {"search": _q("おやすみ")},
    {"search": _q("夜")}, {"search": _q("月")}, {"search": _q("星空")},
    {"search": _q("まどろみ")}, {"search": _q("ほし")}, {"search": _q("癒し")},
    {"search": _q("のんびり")}, {"search": _q("まったり")},
    {"search": "sleep"}, {"search": "chill"}, {"search": "relax"},
    {"search": "cozy"}, {"search": "night"}, {"search": "ambient"},
    {"search": "lounge"}, {"search": "bed"},
    {"tag": "author_tag_sleep"}, {"tag": "author_tag_bed"}, {"tag": "author_tag_chill"},
    {"tag": "author_tag_relax"}, {"tag": "author_tag_cozy"}, {"tag": "author_tag_ambient"},
    {"tag": "author_tag_lounge"},
    {"tag": "author_tag_sleep", "sort": "updated"},
    {"tag": "author_tag_chill", "sort": "updated"},
    {"tag": "author_tag_relax", "sort": "updated"},
]


def _session():
    return AsyncSessionLocal()


def _make_client(cookie: str) -> vrchatapi.ApiClient:
    config = vrchatapi.Configuration()
    client = vrchatapi.ApiClient(config)
    client.user_agent = USER_AGENT
    client.set_default_header("Cookie", f"auth={cookie}")
    return client


def _extract_auth_cookie(headers) -> str | None:
    m = re.search(r"auth=(authcookie_[^;]+)", str((headers or {}).get("Set-Cookie", "")))
    return m.group(1) if m else None


def _extract_twofactor_cookie(headers) -> str | None:
    m = re.search(r"twoFactorAuth=([^;]+)", str((headers or {}).get("Set-Cookie", "")))
    return m.group(1) if m else None


def _verify_cookie_sync(cookie: str) -> bool:
    client = _make_client(cookie)
    try:
        AuthenticationApi(client).get_current_user()
        return True
    except Exception:
        return False


def _password_login_sync(twofactor_cookie: str | None) -> tuple[str, str | None, str | None]:
    """Returns (status, pending_or_auth_cookie, twofactor_cookie).
    status: "ok" | "email_otp"."""
    config = vrchatapi.Configuration()
    client = vrchatapi.ApiClient(config)
    client.user_agent = USER_AGENT
    creds = f"{VRC_USERNAME}:{VRC_PASSWORD}".encode("utf-8")
    client.set_default_header("Authorization", "Basic " + base64.b64encode(creds).decode("ascii"))
    if twofactor_cookie:
        client.set_default_header("Cookie", f"twoFactorAuth={twofactor_cookie}")
    try:
        AuthenticationApi(client).get_current_user()
        # 2FA 不要でログイン成功。Set-Cookie から auth を拾えない実装差異に備え、
        # twoFactorAuth クッキーで再検証してから保存する（呼び出し側で auth 取得）。
        return "ok", twofactor_cookie, twofactor_cookie
    except ApiException as e:
        body = str(getattr(e, "body", "") or "")
        headers = getattr(e, "headers", None)
        auth_cookie = _extract_auth_cookie(headers)
        if "emailOtp" in body or "2 Factor" in body or "requiresTwoFactorAuth" in body:
            return "email_otp", auth_cookie, _extract_twofactor_cookie(headers)
        raise


def _verify_otp_sync(pending_cookie: str, code: str) -> str | None:
    """OTP を検証し twoFactorAuth クッキーを返す。"""
    client = _make_client(pending_cookie)
    api = AuthenticationApi(client)
    api.verify2_fa_email_code(two_factor_email_code=TwoFactorEmailCode(code=code.strip()))
    # 検証後のレスポンスヘッダから twoFactorAuth を取得
    try:
        _, _, headers = api.get_current_user_with_http_info()
    except Exception:
        headers = None
    return _extract_twofactor_cookie(headers)


async def get_active_cookie() -> str | None:
    async with _session() as s:
        cookie = await get_state(s, VRC_AUTH_COOKIE)
        tfa = await get_state(s, VRC_TWOFACTOR_COOKIE)
    if cookie and await asyncio.to_thread(_verify_cookie_sync, cookie):
        return cookie
    # auth 失効 → twoFactorAuth で自動再ログイン
    status, new_cookie, new_tfa = await asyncio.to_thread(_password_login_sync, tfa)
    if status == "ok" and new_cookie:
        async with _session() as s:
            await set_state(s, VRC_AUTH_COOKIE, new_cookie)
            if new_tfa:
                await set_state(s, VRC_TWOFACTOR_COOKIE, new_tfa)
        return new_cookie
    return None


async def login() -> str:
    async with _session() as s:
        saved = await get_state(s, VRC_AUTH_COOKIE)
        tfa = await get_state(s, VRC_TWOFACTOR_COOKIE)
    if saved and await asyncio.to_thread(_verify_cookie_sync, saved):
        return "ok"
    status, cookie, new_tfa = await asyncio.to_thread(_password_login_sync, tfa)
    if status == "ok" and cookie:
        async with _session() as s:
            await set_state(s, VRC_AUTH_COOKIE, cookie)
            if new_tfa:
                await set_state(s, VRC_TWOFACTOR_COOKIE, new_tfa)
        return "ok"
    if cookie:
        async with _session() as s:
            await set_state(s, VRC_PENDING_COOKIE, cookie)
    return "email_otp"


async def verify_email_otp(code: str) -> None:
    async with _session() as s:
        pending = await get_state(s, VRC_PENDING_COOKIE)
    if not pending:
        raise RuntimeError("ログインセッションがありません。再度ログインしてください")
    tfa = await asyncio.to_thread(_verify_otp_sync, pending, code)
    async with _session() as s:
        await set_state(s, VRC_AUTH_COOKIE, pending)
        if tfa:
            await set_state(s, VRC_TWOFACTOR_COOKIE, tfa)
        await delete_state(s, VRC_PENDING_COOKIE)


def _world_to_dict(world) -> dict:
    return {
        "world_id": world.id,
        "name": world.name,
        "author_name": getattr(world, "author_name", ""),
        "description": (getattr(world, "description", None) or "")[:500],
        "image_url": getattr(world, "image_url", None),
        "capacity": getattr(world, "capacity", None),
        "tags": getattr(world, "tags", None),
        "vrc_url": f"https://vrchat.com/home/world/{world.id}",
    }


def get_world(world_id: str, cookie: str) -> dict | None:
    with _make_client(cookie) as api_client:
        try:
            return _world_to_dict(WorldsApi(api_client).get_world(world_id))
        except ApiException:
            return None


def _search_worlds_with_cookie(cookie: str, queries: list[dict]) -> list[dict]:
    seen: set[str] = set()
    results: list[dict] = []
    with _make_client(cookie) as api_client:
        api = WorldsApi(api_client)
        for query in queries:
            try:
                params = {"n": 50, "sort": "heat", "release_status": "public"}
                params.update(query)
                for w in api.search_worlds(**params):
                    if w.id not in seen:
                        seen.add(w.id)
                        results.append(_world_to_dict(w))
            except ApiException:
                continue
    return results
```

> 注: `tags` の JSON 文字列化は `repository.upsert_world` 側で吸収済み（list を受け取れる）。`_world_to_dict` の `tags` は vrchatapi のオブジェクト由来のためそのまま渡し、upsert 側で list なら `json.dumps` される。

- [ ] **Step 4: 実行して成功を確認**

Run: `python -m pytest tests/test_vrc_client.py -v`
Expected: PASS（login 2 ケース + 抽出 2 ケース）

- [ ] **Step 5: Commit**

```bash
git add collector/vrc_client.py tests/test_vrc_client.py
git commit -m "feat: VRChatクッキーをDB管理化しOTPなし自動再ログインに対応"
```

---

## Phase 4: 分割収集パイプライン

### Task 8: run_collection_chunk（カーソル分割）

**Files:**
- Modify: `collector/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `vrc_client.get_active_cookie`, `vrc_client._search_worlds_with_cookie`, `vrc_client.SEARCH_QUERIES`, `ai_scorer.score_worlds`, `db.repository.*`, `db.state.*`。
- Produces: `async def run_collection_chunk() -> dict`（戻り値 `{"status","new","scored","cursor"}`）。1 回の呼び出しで `COLLECT_QUERY_BATCH` 本のクエリ＋1 採点バッチのみ処理。

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_pipeline.py`

`vrc_client` と `ai_scorer` をモックし、カーソルが N 本ずつ進み末尾で 0 に戻ること、`auth_required` 分岐を検証する。

```python
import collector.pipeline as pl
from db.state import COLLECT_CURSOR, get_state, set_state


async def test_auth_required_when_no_cookie(session, monkeypatch):
    monkeypatch.setattr(pl, "_session", lambda: _ctx(session))

    async def _no_cookie():
        return None
    monkeypatch.setattr(pl, "get_active_cookie", _no_cookie)

    out = await pl.run_collection_chunk()
    assert out["status"] == "auth_required"


async def test_cursor_advances_and_wraps(session, monkeypatch):
    monkeypatch.setattr(pl, "_session", lambda: _ctx(session))
    monkeypatch.setattr(pl, "COLLECT_QUERY_BATCH", 2)
    monkeypatch.setattr(pl, "SEARCH_QUERIES", [{"search": "a"}, {"search": "b"}, {"search": "c"}])

    async def _cookie():
        return "authcookie_x"
    monkeypatch.setattr(pl, "get_active_cookie", _cookie)
    monkeypatch.setattr(pl, "_search", lambda cookie, queries: [])
    monkeypatch.setattr(pl, "_score", lambda unscored: [])

    out1 = await pl.run_collection_chunk()
    assert out1["cursor"] == 2
    out2 = await pl.run_collection_chunk()  # 2->超過->0 にラップ
    assert out2["cursor"] == 0


class _ctx:
    def __init__(self, s): self._s = s
    async def __aenter__(self): return self._s
    async def __aexit__(self, *a): return False
```

- [ ] **Step 2: 実行して失敗を確認**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL（`run_collection_chunk` 未定義）

- [ ] **Step 3: collector/pipeline.py を更新**

```python
import asyncio
import os
from datetime import datetime

from collector.ai_scorer import score_worlds
from collector.vrc_client import SEARCH_QUERIES, _search_worlds_with_cookie, get_active_cookie
from db.engine import AsyncSessionLocal
from db.repository import get_unscored_worlds, save_ai_scores, upsert_world
from db.state import COLLECT_CURSOR, LAST_COLLECT_AT, LAST_STATUS, get_state, set_state

COLLECT_QUERY_BATCH = int(os.getenv("COLLECT_QUERY_BATCH", "4"))


def _session():
    return AsyncSessionLocal()


def _search(cookie: str, queries: list[dict]) -> list[dict]:
    return _search_worlds_with_cookie(cookie, queries)


def _score(unscored: list[dict]) -> list[dict]:
    return score_worlds(unscored)


async def run_collection_chunk() -> dict:
    cookie = await get_active_cookie()
    if not cookie:
        async with _session() as s:
            await set_state(s, LAST_STATUS, "auth_required")
        return {"status": "auth_required", "new": 0, "scored": 0, "cursor": -1}

    async with _session() as s:
        cursor = int(await get_state(s, COLLECT_CURSOR) or "0")

    total = len(SEARCH_QUERIES)
    queries = SEARCH_QUERIES[cursor: cursor + COLLECT_QUERY_BATCH]
    next_cursor = cursor + COLLECT_QUERY_BATCH
    if next_cursor >= total:
        next_cursor = 0

    worlds = await asyncio.to_thread(_search, cookie, queries)
    new_count = 0
    for data in worlds:
        async with _session() as s:
            _, created = await upsert_world(s, data)
            if created:
                new_count += 1

    async with _session() as s:
        unscored = await get_unscored_worlds(s)
    scored = 0
    if unscored:
        results = await asyncio.to_thread(_score, unscored)
        async with _session() as s:
            scored = await save_ai_scores(s, results)

    async with _session() as s:
        await set_state(s, COLLECT_CURSOR, str(next_cursor))
        await set_state(s, LAST_COLLECT_AT, datetime.utcnow().isoformat())
        await set_state(s, LAST_STATUS, f"ok new={new_count} scored={scored}")

    return {"status": "ok", "new": new_count, "scored": scored, "cursor": next_cursor}
```

> 既存の `run_collection()` は残してよいが、本番経路は `run_collection_chunk()`。`get_unscored_worlds` が全件返すと採点が長くなるため、採点は 1 バッチ（`BATCH_SIZE`=20）で打ち切られる設計（`score_worlds` の内部ループで時間を食い過ぎる場合は将来 `unscored[:BATCH_SIZE]` に制限。今回は env で `SCORING_BATCH_SIZE` を絞れるため可）。

- [ ] **Step 4: 実行して成功を確認**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS（2 件）

- [ ] **Step 5: Commit**

```bash
git add collector/pipeline.py tests/test_pipeline.py
git commit -m "feat: カーソルで分割実行する run_collection_chunk を追加"
```

---

## Phase 5: Python サーバーレス関数

### Task 9: 共通ヘルパ `api/_shared.py`

**Files:**
- Create: `api/__init__.py`, `api/_shared.py`
- Test: `tests/test_api_shared.py`

**Interfaces:**
- Produces:
  - `def check_admin(headers: dict) -> bool` — `Authorization: Bearer <ADMIN_TOKEN>` または cookie を検証。env `ADMIN_TOKEN`。
  - `def check_cron(headers: dict) -> bool` — `Authorization: Bearer <CRON_SECRET>`。env `CRON_SECRET`。
  - `def json_response(handler, status: int, body: dict) -> None` — `BaseHTTPRequestHandler` にJSONを書く。
  - `async def ensure_db() -> None` — `init_db()` を 1 度だけ呼ぶ（冪等）。

- [ ] **Step 1: 失敗するテストを書く** — `tests/test_api_shared.py`

```python
import os

from api._shared import check_admin, check_cron


def test_check_cron(monkeypatch):
    monkeypatch.setenv("CRON_SECRET", "s3cr3t")
    assert check_cron({"authorization": "Bearer s3cr3t"}) is True
    assert check_cron({"authorization": "Bearer nope"}) is False
    assert check_cron({}) is False


def test_check_admin_bearer(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    assert check_admin({"authorization": "Bearer tok"}) is True
    assert check_admin({"cookie": "admin_token=tok"}) is True
    assert check_admin({"authorization": "Bearer x"}) is False
```

- [ ] **Step 2: 実行して失敗を確認**

Run: `python -m pytest tests/test_api_shared.py -v`
Expected: FAIL（モジュール未作成）

- [ ] **Step 3: api/__init__.py（空）と api/_shared.py を作成**

```python
import json
import os

from db.engine import init_db

_db_ready = False


def _bearer(headers: dict) -> str | None:
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    return auth[len("Bearer "):] if auth.startswith("Bearer ") else None


def _cookie_value(headers: dict, name: str) -> str | None:
    raw = headers.get("cookie") or headers.get("Cookie") or ""
    for part in raw.split(";"):
        k, _, v = part.strip().partition("=")
        if k == name:
            return v
    return None


def check_cron(headers: dict) -> bool:
    secret = os.getenv("CRON_SECRET", "")
    return bool(secret) and _bearer(headers) == secret


def check_admin(headers: dict) -> bool:
    token = os.getenv("ADMIN_TOKEN", "")
    if not token:
        return False
    return _bearer(headers) == token or _cookie_value(headers, "admin_token") == token


def json_response(handler, status: int, body: dict) -> None:
    payload = json.dumps(body).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


async def ensure_db() -> None:
    global _db_ready
    if not _db_ready:
        await init_db()
        _db_ready = True
```

- [ ] **Step 4: 実行して成功を確認**

Run: `python -m pytest tests/test_api_shared.py -v`
Expected: PASS（2 件）

- [ ] **Step 5: Commit**

```bash
git add api/__init__.py api/_shared.py tests/test_api_shared.py
git commit -m "feat: Python関数共通ヘルパ(認証/JSON/DB初期化)を追加"
```

### Task 10: Cron 関数 `api/cron/collect.py`

**Files:**
- Create: `api/cron/__init__.py`, `api/cron/collect.py`

**Interfaces:**
- Consumes: `api._shared`, `collector.pipeline.run_collection_chunk`。
- Produces: Vercel Python ハンドラ `handler(BaseHTTPRequestHandler)`。GET/POST で起動。認証: `check_cron` または `check_admin`（管理画面手動キック用）。

> このタスクは外部 I/O が主でユニットテストは省略（`run_collection_chunk` は Task 8 で検証済み）。ハンドラの構造のみ実装し、ローカル import エラーがないことを確認する。

- [ ] **Step 1: api/cron/__init__.py（空）と api/cron/collect.py を作成**

```python
import asyncio
from http.server import BaseHTTPRequestHandler

from api._shared import check_admin, check_cron, ensure_db, json_response
from collector.pipeline import run_collection_chunk


def _run(handler):
    headers = {k.lower(): v for k, v in handler.headers.items()}
    if not (check_cron(headers) or check_admin(headers)):
        json_response(handler, 401, {"error": "unauthorized"})
        return

    async def _go():
        await ensure_db()
        return await run_collection_chunk()

    result = asyncio.run(_go())
    json_response(handler, 200, result)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _run(self)

    def do_POST(self):
        _run(self)
```

- [ ] **Step 2: import 健全性を確認**

Run: `python -c "import api.cron.collect"`
Expected: エラーなし

- [ ] **Step 3: Commit**

```bash
git add api/cron/__init__.py api/cron/collect.py
git commit -m "feat: Vercel Cron用 収集エンドポイントを追加"
```

### Task 11: VRChat ログイン/OTP 関数

**Files:**
- Create: `api/admin/__init__.py`, `api/admin/vrc_login.py`, `api/admin/vrc_otp.py`

**Interfaces:**
- Consumes: `api._shared`, `collector.vrc_client.login/verify_email_otp`。
- Produces: それぞれ `handler`。`check_admin` 必須。`vrc_login` は POST で `{"status":"ok"|"email_otp"}`。`vrc_otp` は POST body `{"code":"123456"}` で `{"status":"ok"}`。

- [ ] **Step 1: api/admin/__init__.py（空）と vrc_login.py を作成**

```python
import asyncio
from http.server import BaseHTTPRequestHandler

from api._shared import check_admin, ensure_db, json_response
from collector.vrc_client import login


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        headers = {k.lower(): v for k, v in self.headers.items()}
        if not check_admin(headers):
            json_response(self, 401, {"error": "unauthorized"})
            return

        async def _go():
            await ensure_db()
            return await login()

        status = asyncio.run(_go())
        json_response(self, 200, {"status": status})
```

- [ ] **Step 2: api/admin/vrc_otp.py を作成**

```python
import asyncio
import json
from http.server import BaseHTTPRequestHandler

from api._shared import check_admin, ensure_db, json_response
from collector.vrc_client import verify_email_otp


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        headers = {k.lower(): v for k, v in self.headers.items()}
        if not check_admin(headers):
            json_response(self, 401, {"error": "unauthorized"})
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            code = (json.loads(raw or b"{}").get("code") or "").strip()
        except json.JSONDecodeError:
            json_response(self, 400, {"error": "invalid json"})
            return
        if not code:
            json_response(self, 400, {"error": "code required"})
            return

        async def _go():
            await ensure_db()
            await verify_email_otp(code)

        asyncio.run(_go())
        json_response(self, 200, {"status": "ok"})
```

- [ ] **Step 3: import 健全性を確認**

Run: `python -c "import api.admin.vrc_login, api.admin.vrc_otp"`
Expected: エラーなし

- [ ] **Step 4: Commit**

```bash
git add api/admin/__init__.py api/admin/vrc_login.py api/admin/vrc_otp.py
git commit -m "feat: 管理用 VRChatログイン/OTP エンドポイントを追加"
```

---

## Phase 6: Next.js Web アプリ

### Task 12: Next.js スキャフォルド + DB 読み取り

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/next.config.ts`, `web/next-env.d.ts`, `web/lib/db.ts`, `web/lib/worlds.ts`, `web/app/layout.tsx`, `web/app/globals.css`

**Interfaces:**
- Produces:
  - `web/lib/db.ts`: `sql` （`@vercel/postgres`）再エクスポート。
  - `web/lib/worlds.ts`: 型 `World` と `getSuggestedWorlds(count=5): Promise<World[]>`, `getQualifiedWorlds(limit, offset): Promise<World[]>`。

- [ ] **Step 1: web/package.json を作成**

```json
{
  "name": "buisui-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@vercel/postgres": "^0.10.0",
    "next": "^15.1.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "typescript": "^5.7.0"
  }
}
```

- [ ] **Step 2: web/tsconfig.json を作成**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "ES2022"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: web/next.config.ts と next-env.d.ts を作成**

`web/next.config.ts`:
```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: { remotePatterns: [{ protocol: "https", hostname: "**" }] },
};

export default nextConfig;
```

`web/next-env.d.ts`:
```typescript
/// <reference types="next" />
/// <reference types="next/image-types/global" />
```

- [ ] **Step 4: web/lib/db.ts と web/lib/worlds.ts を作成**

`web/lib/db.ts`:
```typescript
import { sql } from "@vercel/postgres";

export { sql };
```

`web/lib/worlds.ts`:
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
};

const QUALIFIED = "ai_sleep_score >= 6 AND ai_is_japanese = 1";

export async function getSuggestedWorlds(count = 5): Promise<World[]> {
  const { rows } = await sql<World>`
    SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url
    FROM worlds
    WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
    ORDER BY RANDOM()
    LIMIT ${count}
  `;
  return rows;
}

export async function getQualifiedWorlds(limit: number, offset: number): Promise<World[]> {
  const { rows } = await sql<World>`
    SELECT world_id, name, author_name, description, image_url, tags, capacity, vrc_url
    FROM worlds
    WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1
    ORDER BY fetched_at DESC NULLS LAST
    LIMIT ${limit} OFFSET ${offset}
  `;
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
```

> `QUALIFIED` 定数は可読性のため定義（未使用なら削除してよい）。クエリにはインライン条件を使用。

- [ ] **Step 5: web/app/layout.tsx と globals.css を作成**

`web/app/globals.css`:
```css
:root { --bg: #0f0c1d; --card: #1a1530; --accent: #7b68ee; --text: #e8e6f0; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; }
a { color: var(--accent); }
```

`web/app/layout.tsx`:
```tsx
import "./globals.css";

export const metadata = { title: "ぶい睡ワールド", description: "VRChat ぶい睡ワールド推薦" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 6: 依存インストールと型チェック**

Run:
```bash
cd web && npm install && npm run typecheck
```
Expected: 型エラーなし（`@vercel/postgres` 等の型が解決）

- [ ] **Step 7: Commit**

```bash
git add web/package.json web/tsconfig.json web/next.config.ts web/next-env.d.ts web/lib web/app/layout.tsx web/app/globals.css web/package-lock.json
git commit -m "feat: Next.jsスキャフォルドとNeon読み取り層を追加"
```

### Task 13: ホーム・一覧・カード

**Files:**
- Create: `web/components/WorldCard.tsx`, `web/app/page.tsx`, `web/app/worlds/page.tsx`

**Interfaces:**
- Consumes: `getSuggestedWorlds`, `getQualifiedWorlds`, `parseTags`, 型 `World`。

- [ ] **Step 1: web/components/WorldCard.tsx を作成**

```tsx
import { parseTags, type World } from "@/lib/worlds";

export function WorldCard({ world }: { world: World }) {
  const tags = parseTags(world.tags);
  return (
    <a
      href={world.vrc_url}
      target="_blank"
      rel="noreferrer"
      style={{
        display: "block", background: "var(--card)", borderRadius: 12,
        overflow: "hidden", textDecoration: "none", color: "var(--text)",
        border: "1px solid #2a2350",
      }}
    >
      {world.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={world.image_url} alt={world.name} style={{ width: "100%", height: 160, objectFit: "cover" }} />
      )}
      <div style={{ padding: 12 }}>
        <div style={{ fontWeight: 700, fontSize: 16 }}>{world.name}</div>
        <div style={{ fontSize: 12, opacity: 0.7, marginTop: 2 }}>by {world.author_name}</div>
        {tags.length > 0 && (
          <div style={{ marginTop: 8, fontSize: 12, color: "var(--accent)" }}>
            {tags.map((t) => `#${t}`).join("　")}
          </div>
        )}
        {world.capacity && (
          <div style={{ marginTop: 6, fontSize: 12, opacity: 0.7 }}>👥 最大 {world.capacity} 人</div>
        )}
      </div>
    </a>
  );
}
```

- [ ] **Step 2: web/app/page.tsx を作成（ホーム・提案）**

```tsx
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
```

- [ ] **Step 3: web/app/worlds/page.tsx を作成（一覧・ページング）**

```tsx
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
```

- [ ] **Step 4: 型チェック**

Run: `cd web && npm run typecheck`
Expected: 型エラーなし

- [ ] **Step 5: Commit**

```bash
git add web/components web/app/page.tsx web/app/worlds
git commit -m "feat: ホーム(提案)・一覧・ワールドカードUIを追加"
```

### Task 14: 管理認証と管理画面

**Files:**
- Create: `web/lib/auth.ts`, `web/middleware.ts`, `web/app/api/admin/login/route.ts`, `web/app/admin/login/page.tsx`, `web/app/admin/page.tsx`

**Interfaces:**
- Consumes: env `ADMIN_PASSWORD`, `ADMIN_TOKEN`。
- Produces: cookie `admin_token` を発行する `/api/admin/login`、`/admin` を middleware で保護。

- [ ] **Step 1: web/lib/auth.ts を作成**

```typescript
export function adminToken(): string {
  return process.env.ADMIN_TOKEN || "";
}

export function adminPassword(): string {
  return process.env.ADMIN_PASSWORD || "";
}

export function isAuthed(token: string | undefined): boolean {
  const expected = adminToken();
  return !!expected && token === expected;
}
```

- [ ] **Step 2: web/middleware.ts を作成**

```typescript
import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  const token = req.cookies.get("admin_token")?.value;
  const expected = process.env.ADMIN_TOKEN;
  if (!expected || token !== expected) {
    const url = req.nextUrl.clone();
    url.pathname = "/admin/login";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/admin"] };
```

- [ ] **Step 3: web/app/api/admin/login/route.ts を作成**

```typescript
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const form = await req.formData();
  const password = String(form.get("password") || "");
  if (!process.env.ADMIN_PASSWORD || password !== process.env.ADMIN_PASSWORD) {
    return NextResponse.redirect(new URL("/admin/login?error=1", req.url), 303);
  }
  const res = NextResponse.redirect(new URL("/admin", req.url), 303);
  res.cookies.set("admin_token", process.env.ADMIN_TOKEN || "", {
    httpOnly: true, secure: true, sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 7,
  });
  return res;
}
```

- [ ] **Step 4: web/app/admin/login/page.tsx を作成**

```tsx
export default async function AdminLogin({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams;
  return (
    <main style={{ maxWidth: 400, margin: "80px auto", padding: 24 }}>
      <h1 style={{ color: "var(--accent)" }}>管理ログイン</h1>
      {error && <p style={{ color: "#ff6b6b" }}>パスワードが違います</p>}
      <form action="/api/admin/login" method="post" style={{ display: "flex", gap: 8 }}>
        <input type="password" name="password" placeholder="パスワード" style={{ flex: 1, padding: 8 }} />
        <button type="submit" style={{ background: "var(--accent)", color: "#fff", border: "none", borderRadius: 8, padding: "8px 16px" }}>
          ログイン
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 5: web/app/admin/page.tsx を作成（状況表示 + 操作）**

```tsx
import { sql } from "@/lib/db";

export const dynamic = "force-dynamic";

async function getStatus() {
  const total = await sql`SELECT COUNT(*)::int AS c FROM worlds`;
  const unscored = await sql`SELECT COUNT(*)::int AS c FROM worlds WHERE ai_sleep_score IS NULL`;
  const qualified = await sql`SELECT COUNT(*)::int AS c FROM worlds WHERE ai_sleep_score >= 6 AND ai_is_japanese = 1`;
  const state = await sql`SELECT key, value FROM app_state WHERE key IN ('last_collect_at','last_status')`;
  const s: Record<string, string> = {};
  for (const r of state.rows) s[r.key as string] = r.value as string;
  return {
    total: total.rows[0].c, unscored: unscored.rows[0].c, qualified: qualified.rows[0].c,
    lastCollectAt: s["last_collect_at"] || "-", lastStatus: s["last_status"] || "-",
  };
}

export default async function Admin() {
  const st = await getStatus();
  return (
    <main style={{ maxWidth: 700, margin: "0 auto", padding: 24 }}>
      <h1 style={{ color: "var(--accent)" }}>管理画面</h1>
      <ul>
        <li>総ワールド数: {st.total}</li>
        <li>未採点: {st.unscored}</li>
        <li>提案対象(qualified): {st.qualified}</li>
        <li>最終収集: {st.lastCollectAt}</li>
        <li>最終ステータス: {st.lastStatus}</li>
      </ul>
      <p style={{ opacity: 0.7, fontSize: 13 }}>
        収集の手動実行・VRChat ログイン/OTP は Python 関数
        <code> /api/cron/collect</code> ・ <code>/api/admin/vrc-login</code> ・ <code>/api/admin/vrc-otp</code>
        を <code>ADMIN_TOKEN</code> 付きで呼び出してください（README 参照）。
      </p>
    </main>
  );
}
```

> 管理画面からの fetch UI（ボタンで Python 関数を叩く）はクライアント JS を足せば実現できるが、YAGNI のため初版は状況表示＋手順案内に留める。

- [ ] **Step 6: 型チェック**

Run: `cd web && npm run typecheck`
Expected: 型エラーなし

- [ ] **Step 7: Commit**

```bash
git add web/lib/auth.ts web/middleware.ts web/app/api web/app/admin
git commit -m "feat: 管理認証(middleware/login)と管理画面を追加"
```

---

## Phase 7: 結線・デプロイ設定

### Task 15: vercel.json と .env.example、README

**Files:**
- Create: `vercel.json`, `DEPLOY.md`
- Modify: `.env.example`

**Interfaces:** なし（設定）。

- [ ] **Step 1: vercel.json を作成**

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "buildCommand": "cd web && npm install && npm run build",
  "outputDirectory": "web/.next",
  "framework": "nextjs",
  "functions": {
    "api/**/*.py": { "runtime": "@vercel/python@4.3.1", "maxDuration": 60 }
  },
  "crons": [
    { "path": "/api/cron/collect", "schedule": "*/10 * * * *" }
  ],
  "rewrites": [
    { "source": "/api/admin/vrc-login", "destination": "/api/admin/vrc_login" },
    { "source": "/api/admin/vrc-otp", "destination": "/api/admin/vrc_otp" }
  ]
}
```

> Next.js を `web/` サブディレクトリに置くため、Vercel プロジェクト設定で Root Directory を `web` にする方法もある。本構成では `vercel.json` の `buildCommand`/`outputDirectory` でリポジトリルートからビルドし、`api/` の Python 関数をルート扱いで同居させる。デプロイ時にどちらが有効かは DEPLOY.md に明記。

- [ ] **Step 2: .env.example に追記**

末尾に追加:

```
# ===== Web版 追加設定 =====
# Neon Postgres 接続文字列（Vercel の Storage から取得）
DATABASE_URL=postgresql://user:password@host/dbname

# nanoGPT（OpenAI互換）
NANOGPT_API_KEY=your_nanogpt_api_key
NANOGPT_BASE_URL=https://nano-gpt.com/api/v1
SCORING_MODEL=gemma
SCORING_BATCH_SIZE=20
COLLECT_QUERY_BATCH=4

# Cron/管理認証
CRON_SECRET=generate_a_long_random_string
ADMIN_TOKEN=generate_a_long_random_string
ADMIN_PASSWORD=your_admin_login_password
```

- [ ] **Step 3: DEPLOY.md を作成**

````markdown
# デプロイ手順（Vercel）

## 1. Neon (Postgres) を用意
Vercel ダッシュボード → Storage → Create Database → Neon。
発行された `DATABASE_URL` をプロジェクトの環境変数に設定。

## 2. 環境変数を設定
`.env.example` の「Web版 追加設定」をすべて Vercel の Environment Variables に登録。
`CRON_SECRET` `ADMIN_TOKEN` は十分長いランダム文字列にする。

## 3. デプロイ
リポジトリを Vercel に接続。`vercel.json` により Next.js(web/) と Python関数(api/) が同居デプロイされる。

## 4. 初回 VRChat ログイン
```bash
curl -X POST https://<your-app>/api/admin/vrc-login -H "Authorization: Bearer $ADMIN_TOKEN"
# => {"status":"email_otp"} ならメールに届いた6桁コードで:
curl -X POST https://<your-app>/api/admin/vrc-otp -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"code":"123456"}'
# => {"status":"ok"}
```

## 5. 収集の確認
Cron は 10 分間隔で `/api/cron/collect` を叩く。手動実行:
```bash
curl -X POST https://<your-app>/api/cron/collect -H "Authorization: Bearer $ADMIN_TOKEN"
```
`/admin`（要ログイン）で収集状況を確認。

## 6. 再認証が必要になったら
`last_status` が `auth_required` になったら手順 4 を再実行（OTP を再入力）。
通常は `twoFactorAuth` クッキーで自動再ログインされるため最長 ~30 日に 1 度程度。
````

- [ ] **Step 4: Commit**

```bash
git add vercel.json .env.example DEPLOY.md
git commit -m "feat: vercel.json・デプロイ手順・env雛形を追加"
```

### Task 16: 全テスト通過と最終確認

**Files:** なし（検証のみ）

- [ ] **Step 1: Python 全テスト**

Run: `python -m pytest -v`
Expected: 全 PASS

- [ ] **Step 2: Web 型チェック + ビルド**

Run: `cd web && npm run typecheck && npm run build`
Expected: 型エラーなし、ビルド成功（DB 接続は build 時不要＝全ページ `force-dynamic`）

- [ ] **Step 3: import 健全性（Python 関数）**

Run: `python -c "import api.cron.collect, api.admin.vrc_login, api.admin.vrc_otp"`
Expected: エラーなし

- [ ] **Step 4: 最終コミット**

```bash
git add -A
git commit -m "chore: Webアプリ化の最終確認"
```

---

## Self-Review（計画作成者によるスペック突合）

- **Web 機能=閲覧・提案**: Task 13（ホーム提案・一覧）でカバー。✓
- **Collector=Vercel Cron 分割実行**: Task 8（chunk）+ Task 10（cron 関数）+ Task 15（cron 設定）。✓
- **スタック=Next.js(TS)**: Task 12–14。✓
- **DB=Neon Postgres**: Task 4（asyncpg 正規化）+ Task 12（@vercel/postgres）。✓
- **AI=nanoGPT/gemma 採点のみ**: Task 6。✓
- **公開=閲覧公開/管理要認証**: Task 14（middleware）+ Task 9（関数側認証）。✓
- **VRChat クッキー DB 化 + twoFactorAuth 自動再ログイン**: Task 7。✓
- **OTP 2 ステップ**: Task 11。✓
- **時間制限対策（有界実行）**: Task 8（カーソル）+ `SCORING_BATCH_SIZE`/`COLLECT_QUERY_BATCH`。✓
- **app_state スキーマ**: Task 2/3。✓
- **X collector/Discord Bot は不変更**: Global Constraints に明記、対象タスクなし。✓
- **型整合**: `World`(TS) と `worlds` 列、`run_collection_chunk` 戻り値キー、`login/verify_email_otp` シグネチャ、`check_admin/check_cron` を各所で一致確認。✓
- プレースホルダ無し。各コードステップに実コードを記載。✓
