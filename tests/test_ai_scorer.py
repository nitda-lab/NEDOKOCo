from collector.ai_scorer import _build_world_summary, _extract_json_array


def test_extract_json_array_with_surrounding_text():
    raw = ' here you go: [{"world_id":"a","is_japanese":true,"sleep_score":8}] done'
    out = _extract_json_array(raw)
    assert out == [{"world_id": "a", "is_japanese": True, "sleep_score": 8}]


def test_extract_json_array_invalid_returns_empty():
    assert _extract_json_array("no json here") == []
    assert _extract_json_array("[broken") == []


def test_extract_json_array_prefers_scored_over_echo():
    raw = (
        "入力を解析します。\n### 入力\n```json\n"
        '[{"world_id":"w1","name":"x","tags":["sleep"]}]\n```\n'
        "### 出力\n```json\n"
        '[{"world_id":"w1","is_japanese":true,"sleep_score":8}]\n```\n以上です。'
    )
    out = _extract_json_array(raw)
    assert out == [{"world_id": "w1", "is_japanese": True, "sleep_score": 8}]


def test_build_world_summary_filters_system_tags():
    s = _build_world_summary({
        "world_id": "a", "name": "n", "author_name": "x",
        "tags": '["system_approved", "chill"]',
    })
    assert s["tags"] == ["chill"]
