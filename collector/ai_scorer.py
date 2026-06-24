import json
import os

from openai import OpenAI

NANOGPT_API_KEY = os.getenv("NANOGPT_API_KEY", "")
NANOGPT_BASE_URL = os.getenv("NANOGPT_BASE_URL", "https://nano-gpt.com/api/v1")
MODEL = os.getenv("SCORING_MODEL", "google/gemma-4-31b-it")
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

重要: 出力はJSON配列のみ。前置き・説明・マークダウンのコードフェンス(```)・入力の再掲は一切禁止。

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
    """饒舌なモデル出力（入力エコー・説明文・```json```）からも採点配列を取り出す。
    バランスした最上位の [...] を全て拾い、sleep_score を含む配列を優先採用する。"""
    candidates: list[str] = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(raw):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]" and depth > 0:
            depth -= 1
            if depth == 0 and start != -1:
                candidates.append(raw[start:i + 1])

    parsed_lists: list[list] = []
    for c in candidates:
        try:
            v = json.loads(c)
        except json.JSONDecodeError:
            continue
        if isinstance(v, list):
            parsed_lists.append(v)

    for v in parsed_lists:
        if v and isinstance(v[0], dict) and "sleep_score" in v[0]:
            return v
    return parsed_lists[-1] if parsed_lists else []


def score_worlds(worlds: list[dict]) -> list[dict]:
    """nanoGPT経由でワールドを一括評価。失敗バッチはスキップ。"""
    if not NANOGPT_API_KEY:
        raise RuntimeError("NANOGPT_API_KEY が設定されていません")

    client = OpenAI(api_key=NANOGPT_API_KEY, base_url=NANOGPT_BASE_URL, timeout=40.0, max_retries=0)
    results: list[dict] = []

    for i in range(0, len(worlds), BATCH_SIZE):
        batch = worlds[i: i + BATCH_SIZE]
        summaries = [_build_world_summary(w) for w in batch]
        worlds_json = json.dumps(summaries, ensure_ascii=False, indent=None)
        try:
            response = client.chat.completions.create(
                model=MODEL,
                max_tokens=4096,
                temperature=0,
                messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(worlds_json=worlds_json)}],
            )
            results.extend(_extract_json_array(response.choices[0].message.content.strip()))
        except Exception:
            continue

    return results
