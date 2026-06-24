import asyncio
from http.server import BaseHTTPRequestHandler

from api._shared import check_admin, check_cron, ensure_db, json_response
from collector.pipeline import run_collection_chunk


def _run(handler):
    headers = {k.lower(): v for k, v in handler.headers.items()}
    if not (check_cron(headers) or check_admin(headers)):
        json_response(handler, 401, {"error": "unauthorized"})
        return

    async def _go():
        await ensure_db()
        return await run_collection_chunk()

    result = asyncio.run(_go())
    json_response(handler, 200, result)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        _run(self)

    def do_POST(self):
        _run(self)
