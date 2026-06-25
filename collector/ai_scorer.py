import json
import os

from openai import OpenAI

NANOGPT_API_KEY = os.getenv("NANOGPT_API_KEY", "")
NANOGPT_BASE_URL = os.getenv("NANOGPT_BASE_URL", "https://nano-gpt.com/api/v1")
MODEL = os.getenv("SCORING_MODEL", "google/gemma-4-31b-it")
BATCH_SIZE = int(os.getenv("SCORING_BATCH_SIZE", "20"))

PROMPT_TEMPLATE = """\
あなたはVRChatの「ぶい睡（VR睡眠）」専門キュレーターです。
ぶい睡とは「そのワールド内で実際に横になって眠ること」を指します。
以下のワールドを評価し、必ず指定のJSONのみを返してください（説明文不要）。

評価項目:
- is_japanese: 日本/アジア圏ユーザー向けか（bool）。作者名やワールド名に日本語があれば true。英語名でも日本語コミュニティ向けなら true。
- sleep_score: その空間で「実際に横になって眠る」のにどれだけ適しているか（整数 1〜10）。名前・タグ・説明文から判断。
  9-10: 明確に就寝向け。ベッド/布団/寝床がある、暗め/間接照明、静かで落ち着く、安眠/ヒーリング、横になれる夜空・星空
  6-8: 静かでくつろげる個人宅・和室など、眠るのにも使えそうな落ち着いた空間
  3-5: 雰囲気はあるが眠る用途ではない
  1-2: ぶい睡に不向き。次は必ず低評価(1-2)にする:
       ラウンジ/カフェ/バー/クラブ/イベント会場/ギャラリー/博物館/撮影スポット/ゲーム/アニメ等の作品テーマ/リミナルスペース/にぎやか・社交メインの空間
  注意: 「chill」「lounge」「cozy」等の語があっても、社交・鑑賞・撮影が主目的なら低評価にする。「眠れるか」だけで判断すること。

返答形式（このJSONオブジェクトのみ、余分なテキスト禁止）:
{{"results":[{{"world_id":"...","is_japanese":true,"sleep_score":8}}, ...]}}

ワールドリスト:
{worlds_json}"""

_ADULT_TAGS = ("content_sex", "content_adult")


def _is_adult(tags_raw) -> bool:
    try:
        raw = json.loads(tags_raw) if isinstance(tags_raw, str) else (tags_raw or [])
        return any(isinstance(t, str) and t in _ADULT_TAGS for t in raw)
    except Exception:
        return False


def _apply_adult_override(results: list[dict], worlds: list[dict]) -> list[dict]:
    """アダルトタグを持つワールドは sleep_score=0 に固定し、適合から除外する。"""
    adult_ids = {w["world_id"] for w in worlds if _is_adult(w.get("tags"))}
    by_id = {r.get("world_id"): r for r in results if isinstance(r, dict)}
    for wid in adult_ids:
        if wid in by_id:
            by_id[wid]["sleep_score"] = 0
        else:
            results.append({"world_id": wid, "is_japanese": False, "sleep_score": 0})
    return results


def _build_world_summary(world: dict) -> dict:
    tags_raw = world.get("tags") or "[]"
    try:
        raw = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
        # 作者が付けた説明的タグ(author_tag_*)だけ残し接頭辞を除去。
        # system_/admin_/feature_/content_/debug_ 等のノイズタグは捨てる。
        tags = [t[len("author_tag_"):] for t in raw if isinstance(t, str) and t.startswith("author_tag_")]
    except Exception:
        tags = []
    return {
        "world_id": world["world_id"],
        "name": world["name"],
        "author": world.get("author_name", ""),
        "tags": tags[:10],
        "description": (world.get("description") or "")[:300],
    }


def _parse_scores(raw: str) -> list[dict]:
    """JSONモードの {"results":[...]} を優先し、配列直返し・饒舌出力にもフォールバックする。"""
    try:
        v = json.loads(raw.strip())
        if isinstance(v, dict):
            for key in ("results", "worlds", "data", "scores"):
                if isinstance(v.get(key), list):
                    return v[key]
        if isinstance(v, list):
            return v
    except json.JSONDecodeError:
        pass
    return _extract_json_array(raw)


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

    client = OpenAI(api_key=NANOGPT_API_KEY, base_url=NANOGPT_BASE_URL, timeout=20.0, max_retries=0)
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
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": PROMPT_TEMPLATE.format(worlds_json=worlds_json)}],
                timeout=20.0,
            )
            results.extend(_parse_scores(response.choices[0].message.content.strip()))
        except Exception:
            continue

    return _apply_adult_override(results, worlds)
