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
REQ_TIMEOUT = 12  # VRChat呼び出しがサーバーレスでハングしないよう全呼び出しに付与


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


def _jar_cookie(client: vrchatapi.ApiClient, name: str) -> str | None:
    for c in client.rest_client.cookie_jar:
        if c.name == name:
            return c.value
    return None


def _verify_cookie_sync(cookie: str) -> bool:
    client = _make_client(cookie)
    try:
        AuthenticationApi(client).get_current_user(_request_timeout=REQ_TIMEOUT)
        return True
    except Exception:
        return False


def _password_login_sync(twofactor_cookie: str | None) -> tuple[str, str | None, str | None]:
    """Returns (status, auth_or_pending_cookie, twofactor_cookie). status: "ok" | "email_otp"."""
    config = vrchatapi.Configuration()
    client = vrchatapi.ApiClient(config)
    client.user_agent = USER_AGENT
    creds = f"{VRC_USERNAME}:{VRC_PASSWORD}".encode("utf-8")
    client.set_default_header("Authorization", "Basic " + base64.b64encode(creds).decode("ascii"))
    if twofactor_cookie:
        client.set_default_header("Cookie", f"twoFactorAuth={twofactor_cookie}")
    try:
        AuthenticationApi(client).get_current_user(_request_timeout=REQ_TIMEOUT)
        return "ok", _jar_cookie(client, "auth"), _jar_cookie(client, "twoFactorAuth") or twofactor_cookie
    except ApiException as e:
        body = str(getattr(e, "body", "") or "").lower()
        if "invalid" in body and ("password" in body or "username" in body or "email or" in body):
            raise
        auth_cookie = _jar_cookie(client, "auth") or _extract_auth_cookie(getattr(e, "headers", None))
        return "email_otp", auth_cookie, _jar_cookie(client, "twoFactorAuth")


def _verify_otp_sync(pending_cookie: str, code: str) -> str | None:
    """OTP を検証し twoFactorAuth クッキーを返す。"""
    client = _make_client(pending_cookie)
    api = AuthenticationApi(client)
    api.verify2_fa_email_code(two_factor_email_code=TwoFactorEmailCode(code=code.strip()))
    try:
        api.get_current_user(_request_timeout=REQ_TIMEOUT)
    except Exception:
        pass
    return _jar_cookie(client, "twoFactorAuth")


async def get_active_cookie() -> str | None:
    """cron用。保存済みauthが有効ならそれを使う。失効時はtwoFactorAuthがある場合のみ
    静かに再ログイン。未ログイン(tfa無し)ならVRChatを叩かず None を返す（OTP乱発・レート制限を避ける）。"""
    async with _session() as s:
        cookie = await get_state(s, VRC_AUTH_COOKIE)
        tfa = await get_state(s, VRC_TWOFACTOR_COOKIE)
    if cookie and await asyncio.to_thread(_verify_cookie_sync, cookie):
        return cookie
    if not tfa:
        return None
    try:
        status, new_cookie, new_tfa = await asyncio.to_thread(_password_login_sync, tfa)
    except ApiException:
        return None
    if status == "ok" and new_cookie:
        async with _session() as s:
            await set_state(s, VRC_AUTH_COOKIE, new_cookie)
            if new_tfa:
                await set_state(s, VRC_TWOFACTOR_COOKIE, new_tfa)
        return new_cookie
    return None


async def login() -> str:
    """管理者用。フルのパスワードログインを行う（メールOTPを誘発しうる）。"""
    async with _session() as s:
        saved = await get_state(s, VRC_AUTH_COOKIE)
        tfa = await get_state(s, VRC_TWOFACTOR_COOKIE)
    if saved and await asyncio.to_thread(_verify_cookie_sync, saved):
        return "ok"
    try:
        status, cookie, new_tfa = await asyncio.to_thread(_password_login_sync, tfa)
    except ApiException as e:
        if getattr(e, "status", None) == 429:
            return "rate_limited"
        raise
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


async def set_auth_cookies(auth: str, twofactor: str | None = None) -> bool:
    """ブラウザ等で取得済みの auth クッキーを検証して保存する。有効なら True。"""
    auth = (auth or "").strip()
    if not auth.startswith("authcookie_"):
        return False
    if not await asyncio.to_thread(_verify_cookie_sync, auth):
        return False
    async with _session() as s:
        await set_state(s, VRC_AUTH_COOKIE, auth)
        if twofactor and twofactor.strip():
            await set_state(s, VRC_TWOFACTOR_COOKIE, twofactor.strip())
        await delete_state(s, VRC_PENDING_COOKIE)
    return True


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
        "vrc_updated_at": getattr(world, "updated_at", None),
        "favorites": getattr(world, "favorites", None),
        "popularity": getattr(world, "popularity", None),
    }


def get_world(world_id: str, cookie: str) -> dict | None:
    with _make_client(cookie) as api_client:
        try:
            return _world_to_dict(WorldsApi(api_client).get_world(world_id, _request_timeout=REQ_TIMEOUT))
        except ApiException:
            return None


def _search_worlds_with_cookie(cookie: str, queries: list[dict]) -> list[dict]:
    seen: set[str] = set()
    results: list[dict] = []
    with _make_client(cookie) as api_client:
        api = WorldsApi(api_client)
        for query in queries:
            try:
                params = {"n": 50, "sort": "heat", "release_status": "public", "_request_timeout": REQ_TIMEOUT}
                params.update(query)
                for w in api.search_worlds(**params):
                    if w.id not in seen:
                        seen.add(w.id)
                        results.append(_world_to_dict(w))
            except ApiException:
                continue
    return results
