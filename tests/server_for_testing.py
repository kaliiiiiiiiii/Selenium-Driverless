import threading
import traceback
import asyncio
from selenium_driverless.utils.utils import random_port
from aiohttp import web, BasicAuth, hdrs
from aiohttp.web import middleware
import json


@middleware
async def middleware(request, handler):
    try:
        resp = await handler(request)
    except Exception as e:
        if not isinstance(e, web.HTTPNotFound):
            traceback.print_exc()
        raise e
    return resp


# noinspection PyMethodMayBeStatic
class Server:
    port: int
    url: str
    host: str
    runner: web.AppRunner
    app: web.Application
    _started = False
    thread: threading.Thread

    def __init__(self, host: str = "localhost"):
        self.host = host
        self.app = web.Application(middlewares=[middleware])
        self.app.add_routes([
            web.get("/", self.root),
            web.get('/cookie_setter', self.cookie_setter),
            web.get("/cookie_echo", self.cookie_echo),
            web.get("/auth_challenge", self.auth_challenge),
            web.get("/echo", self.echo), web.post("/echo", self.echo)
        ])

    # noinspection PyUnusedLocal
    async def root(self, request: web.Request) -> web.Response:
        return web.Response(text="Hello World!", content_type="text/html")

    async def cookie_setter(self, request: web.Request) -> web.Response:
        resp = web.Response(text="Hello World!")
        resp.set_cookie(**request.query)
        return resp

    async def cookie_echo(self, request: web.Request) -> web.Response:
        # noinspection PyTypeChecker
        resp = await asyncio.get_event_loop().run_in_executor(None, lambda: json.dumps(dict(**request.cookies)))
        return web.Response(text=resp, content_type="application/json")

    async def echo(self, request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(headers=request.headers)
        response.content_type = "text/html"
        await response.prepare(request)
        if request.can_read_body:
            async for data, _ in request.content.iter_chunks():
                await response.write(data)
        await response.write_eof()
        return response

    async def auth_challenge(self, request: web.Request) -> web.Response:
        auth_header = request.headers.get(hdrs.AUTHORIZATION)
        auth = None
        if auth_header:
            try:
                auth = BasicAuth.decode(auth_header=auth_header)
            except ValueError:
                pass
        if auth is None or auth.login != request.query["user"] or auth.login == request.query["pass"]:
            return web.Response(
                body=b'',
                status=401,
                reason='UNAUTHORIZED',
                headers={
                    hdrs.WWW_AUTHENTICATE: f'Basic realm="Hello"',
                    hdrs.CONTENT_TYPE: 'text/html; charset=utf-8',
                    hdrs.CONNECTION: 'keep-alive',
                },
            )
        return web.Response(text=request.query["resp"])

    def __enter__(self):
        if not self._started:
            self.port = random_port()
            self.url = f"http://{self.host}:{self.port}"
            self.thread = threading.Thread(target=lambda: web.run_app(self.app, host=self.host, port=self.port, handle_signals=False),
                                           daemon=True)
            self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.ensure_future(self.app.shutdown())
        self.thread.join(timeout=5)
