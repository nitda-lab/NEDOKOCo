import asyncio
import json
import traceback
from http.server import BaseHTTPRequestHandler

from api._shared import check_admin, ensure_db, json_response
from collector.vrc_client import verify_email_otp


def _mask(v):
    if not v:
        return None
    return f"{v[:14]}...len={len(v)}"


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

        if code == "__status__":
            async def _dbg():
                await ensure_db()
                from db.engine import AsyncSessionLocal
                from db.state import (VRC_AUTH_COOKIE, VRC_PENDING_COOKIE,
                                      VRC_TWOFACTOR_COOKIE, get_state)
                async with AsyncSessionLocal() as s:
                    return {
                        "pending": _mask(await get_state(s, VRC_PENDING_COOKIE)),
                        "auth": _mask(await get_state(s, VRC_AUTH_COOKIE)),
                        "twofactor": _mask(await get_state(s, VRC_TWOFACTOR_COOKIE)),
                    }
            try:
                json_response(self, 200, asyncio.run(_dbg()))
            except Exception as e:
                json_response(self, 500, {"error": type(e).__name__, "message": str(e)})
            return

        if not code:
            json_response(self, 400, {"error": "code required"})
            return

        async def _go():
            await ensure_db()
            await verify_email_otp(code)

        try:
            asyncio.run(_go())
            json_response(self, 200, {"status": "ok"})
        except Exception as e:
            json_response(self, 500, {
                "error": type(e).__name__,
                "message": str(e),
                "trace": traceback.format_exc()[-1500:],
            })
