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
