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
