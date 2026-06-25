from collector.ai_scorer import _build_world_summary, _extract_json_array, _parse_scores


def test_parse_scores_json_object():
    raw = '{"results":[{"world_id":"a","is_japanese":true,"sleep_score":8}]}'
    assert _parse_scores(raw) == [{"world_id": "a", "is_japanese": True, "sleep_score": 8}]


def test_parse_scores_plain_array():
    raw = '[{"world_id":"a","is_japanese":false,"sleep_score":3}]'
    assert _parse_scores(raw) == [{"world_id": "a", "is_japanese": False, "sleep_score": 3}]


def test_parse_scores_fallback_chatty():
    raw = 'ok: {"results":[{"world_id":"a","is_japanese":true,"sleep_score":5}]} done'
    assert _parse_scores(raw) == [{"world_id": "a", "is_japanese": True, "sleep_score": 5}]


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


def test_build_world_summary_keeps_only_author_tags():
    s = _build_world_summary({
        "world_id": "a", "name": "n", "author_name": "x",
        "tags": '["system_approved", "author_tag_chill", "admin_x", "content_adult"]',
    })
    assert s["tags"] == ["chill"]


def test_is_adult():
    from collector.ai_scorer import _is_adult

    assert _is_adult('["content_adult", "author_tag_chill"]') is True
    assert _is_adult('["content_sex"]') is True
    assert _is_adult('["author_tag_sleep"]') is False
    assert _is_adult(None) is False


def test_apply_adult_override():
    from collector.ai_scorer import _apply_adult_override

    worlds = [
        {"world_id": "a", "tags": '["content_adult"]'},
        {"world_id": "b", "tags": '["author_tag_sleep"]'},
        {"world_id": "c", "tags": '["content_sex"]'},
    ]
    results = [
        {"world_id": "a", "is_japanese": True, "sleep_score": 9},
        {"world_id": "b", "is_japanese": True, "sleep_score": 8},
    ]
    out = _apply_adult_override(results, worlds)
    by = {r["world_id"]: r for r in out}
    assert by["a"]["sleep_score"] == 0
    assert by["b"]["sleep_score"] == 8
    assert by["c"]["sleep_score"] == 0


def test_build_world_summary_includes_description():
    s = _build_world_summary({
        "world_id": "a", "name": "n", "author_name": "x",
        "tags": "[]", "description": "ベッドあり 寝落ち歓迎",
    })
    assert s["description"] == "ベッドあり 寝落ち歓迎"
