import asyncio
from http.server import BaseHTTPRequestHandler

from api._shared import check_admin, ensure_db, json_response
from collector.vrc_client import login


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        headers = {k.lower(): v for k, v in self.headers.items()}
        if not check_admin(headers):
            json_response(self, 401, {"error": "unauthorized"})
            return

        async def _go():
            await ensure_db()
            return await login()

        status = asyncio.run(_go())
        json_response(self, 200, {"status": status})
