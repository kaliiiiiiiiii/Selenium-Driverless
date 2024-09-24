import threading
import traceback
import asyncio
from selenium_driverless.utils.utils import random_port
from aiohttp import web
from aiohttp.web import middleware


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
            web.get('/cookie_setter', self.cookie_setter)
        ])

    async def cookie_setter(self, request: web.Request) -> web.Response:
        resp = web.Response(text="Hello World!")
        resp.set_cookie(**request.query)
        return resp

    def __enter__(self):
        if not self._started:
            self.port = random_port()
            self.url = f"http://{self.host}:{self.port}"
            self.thread = threading.Thread(target=lambda: web.run_app(self.app, host=self.host, port=self.port),
                                           daemon=True)
            self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.ensure_future(self.app.shutdown())
        self.thread.join(timeout=5)
