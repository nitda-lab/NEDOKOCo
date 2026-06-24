import asyncio
import json
import traceback
from http.server import BaseHTTPRequestHandler

from api._shared import check_admin, ensure_db, json_response
from collector.vrc_client import set_auth_cookies


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        headers = {k.lower(): v for k, v in self.headers.items()}
        if not check_admin(headers):
            json_response(self, 401, {"error": "unauthorized"})
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            json_response(self, 400, {"error": "invalid json"})
            return
        auth = (data.get("auth") or "").strip()
        twofactor = (data.get("twofactor") or "").strip() or None
        if not auth:
            json_response(self, 400, {"error": "auth required"})
            return

        async def _go():
            await ensure_db()
            return await set_auth_cookies(auth, twofactor)

        try:
            valid = asyncio.run(_go())
            json_response(self, 200 if valid else 400, {"valid": valid})
        except Exception as e:
            json_response(self, 500, {
                "error": type(e).__name__,
                "message": str(e),
                "trace": traceback.format_exc()[-1500:],
            })
