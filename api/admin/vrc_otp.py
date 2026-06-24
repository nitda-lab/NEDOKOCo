import asyncio
import json
from http.server import BaseHTTPRequestHandler

from api._shared import check_admin, ensure_db, json_response
from collector.vrc_client import verify_email_otp


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
        if not code:
            json_response(self, 400, {"error": "code required"})
            return

        async def _go():
            await ensure_db()
            await verify_email_otp(code)

        asyncio.run(_go())
        json_response(self, 200, {"status": "ok"})
