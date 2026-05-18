import base64
import os
import re
from urllib.parse import quote

import vrchatapi
from vrchatapi.api import AuthenticationApi, WorldsApi
from vrchatapi.exceptions import ApiException

VRC_USERNAME = os.getenv("VRC_USERNAME", "")
VRC_PASSWORD = os.getenv("VRC_PASSWORD", "")
AUTH_COOKIE_PATH = "data/vrc_auth.cookie"
PENDING_COOKIE_PATH = "data/vrc_pending.cookie"

_pending_client: vrchatapi.ApiClient | None = None
_pending_auth_cookie: str | None = None


def _q(text: str) -> str:
    return quote(text, safe="", encoding="utf-8")


SEARCH_QUERIES: list[dict] = [
    # ぶい睡系
    {"search": _q("ぶい睡")},
    {"search": _q("ぶいすい")},
    {"search": "buisui"},
    {"search": _q("VR睡眠")},
    # 日本語睡眠・夜・安らぎ系
    {"search": _q("睡眠")},
    {"search": _q("おやすみ")},
    {"search": _q("夜")},
    {"search": _q("月")},
    {"search": _q("星空")},
    {"search": _q("まどろみ")},
    {"search": _q("ほし")},
    {"search": _q("癒し")},
    {"search": _q("のんびり")},
    {"search": _q("まったり")},
    # 英語系
    {"search": "sleep"},
    {"search": "chill"},
    {"search": "relax"},
    {"search": "cozy"},
    {"search": "night"},
    {"search": "ambient"},
    {"search": "lounge"},
    {"search": "bed"},
    # タグ系（heat順）
    {"tag": "author_tag_sleep"},
    {"tag": "author_tag_bed"},
    {"tag": "author_tag_chill"},
    {"tag": "author_tag_relax"},
    {"tag": "author_tag_cozy"},
    {"tag": "author_tag_ambient"},
    {"tag": "author_tag_lounge"},
    # タグ系（recent順で別セット）
    {"tag": "author_tag_sleep", "sort": "updated"},
    {"tag": "author_tag_chill", "sort": "updated"},
    {"tag": "author_tag_relax", "sort": "updated"},
]


def _load_file(path: str) -> str | None:
    try:
        with open(path) as f:
            v = f.read().strip()
            return v if v.startswith("authcookie_") else None
    except FileNotFoundError:
        return None


def _save_file(path: str, value: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(value)


def _delete_file(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _make_client(cookie: str) -> vrchatapi.ApiClient:
    config = vrchatapi.Configuration()
    client = vrchatapi.ApiClient(config)
    client.user_agent = "buisui-bot/1.0 smileglass314@gmail.com"
    client.set_default_header("Cookie", f"auth={cookie}")
    return client


def _extract_cookie(headers) -> str | None:
    set_cookie = str((headers or {}).get("Set-Cookie", ""))
    m = re.search(r"auth=(authcookie_[^;]+)", set_cookie)
    return m.group(1) if m else None


def login() -> str:
    """
    VRChatへのログインを試みる。
    Returns: "ok" | "email_otp"
    """
    global _pending_client, _pending_auth_cookie

    # すでにOTP待ち状態ならそのまま返す（新たなログイン試行をしない）
    pending_cookie = _load_file(PENDING_COOKIE_PATH)
    if pending_cookie:
        _pending_auth_cookie = pending_cookie
        _pending_client = _make_client(pending_cookie)
        return "email_otp"

    # 保存済み認証クッキーを試す
    saved = _load_file(AUTH_COOKIE_PATH)
    if saved:
        client = _make_client(saved)
        try:
            AuthenticationApi(client).get_current_user()
            return "ok"
        except Exception:
            _delete_file(AUTH_COOKIE_PATH)

    # 新規ログイン
    config = vrchatapi.Configuration()
    client = vrchatapi.ApiClient(config)
    client.user_agent = "buisui-bot/1.0 smileglass314@gmail.com"
    creds = f"{VRC_USERNAME}:{VRC_PASSWORD}".encode("utf-8")
    client.set_default_header("Authorization", "Basic " + base64.b64encode(creds).decode("ascii"))

    try:
        AuthenticationApi(client).get_current_user()
        return "ok"
    except ApiException as e:
        body = str(getattr(e, "body", "") or "")
        headers = getattr(e, "headers", None)
        cookie = _extract_cookie(headers)
        if "emailOtp" in body:
            if cookie:
                _pending_auth_cookie = cookie
                _save_file(PENDING_COOKIE_PATH, cookie)
                client.set_default_header("Cookie", f"auth={cookie}")
            _pending_client = client
            return "email_otp"
        raise


def verify_email_otp(code: str) -> None:
    """メールOTPで認証を完了し、クッキーを保存する"""
    from vrchatapi.models import TwoFactorEmailCode

    global _pending_client, _pending_auth_cookie

    cookie = _pending_auth_cookie or _load_file(PENDING_COOKIE_PATH)
    if not cookie:
        raise RuntimeError("ログインセッションがありません。Botを再起動してください")

    # Basic Auth ヘッダーを含まないクリーンなクライアントで検証する
    client = _make_client(cookie)

    AuthenticationApi(client).verify2_fa_email_code(
        two_factor_email_code=TwoFactorEmailCode(code=code.strip())
    )

    _save_file(AUTH_COOKIE_PATH, cookie)
    _delete_file(PENDING_COOKIE_PATH)
    _pending_client = None
    _pending_auth_cookie = None


def _worlds_client() -> vrchatapi.ApiClient:
    cookie = _load_file(AUTH_COOKIE_PATH)
    if not cookie:
        raise RuntimeError("VRChatにログインしていません。/admin vrc_login でOTPを入力してください")
    return _make_client(cookie)


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


def get_world(world_id: str) -> dict | None:
    with _worlds_client() as api_client:
        try:
            return _world_to_dict(WorldsApi(api_client).get_world(world_id))
        except ApiException:
            return None


def search_worlds() -> list[dict]:
    seen: set[str] = set()
    results: list[dict] = []

    with _worlds_client() as api_client:
        api = WorldsApi(api_client)
        for query in SEARCH_QUERIES:
            try:
                params = {"n": 50, "sort": "heat", "release_status": "public"}
                params.update(query)
                worlds = api.search_worlds(**params)
                for w in worlds:
                    if w.id not in seen:
                        seen.add(w.id)
                        results.append(_world_to_dict(w))
            except ApiException:
                continue

    return results
