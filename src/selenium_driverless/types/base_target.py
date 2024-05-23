import asyncio
import time
import typing

import aiohttp
import websockets
from cdp_socket.exceptions import CDPError
from cdp_socket.socket import SingleCDPSocket


class BaseTarget:
    """the baseTarget for the ChromeInstance
    represents a connection to the whole browser.

    .. note::
        commands executed on BaseTarget usually are on a global scope over the whole Chrome instance.
        unfortunately, not all are supported

    """

    # noinspection PyMissingConstructor
    def __init__(self, host: str, is_remote: bool = False,
                 loop: asyncio.AbstractEventLoop or None = None, timeout: float = 30,
                 max_ws_size: int = 2 ** 20) -> None:
        self._socket = None

        self._is_remote = is_remote
        self._host = host
        self._id = "BaseTarget"

        self._loop = loop
        self._started = False
        self._timeout = timeout
        self._max_ws_size = max_ws_size
        self._downloads_paths = {}

    def __repr__(self):
        return f'<{type(self).__module__}.{type(self).__name__} (target_id="{self.id}", host="{self._host}")>'

    @property
    def id(self):
        return self._id

    @property
    async def type(self):
        return "BaseTarget"

    @property
    def socket(self) -> SingleCDPSocket:
        """the cdp-socket for the connection"""
        return self._socket

    async def __aenter__(self):
        await self._init()
        return self

    def __enter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __await__(self):
        return self._init().__await__()

    async def _init(self):
        if not self._started:
            start = time.perf_counter()
            url = f"http://{self._host}/json/version"
            while True:
                try:
                    async with aiohttp.ClientSession() as session:
                        res = await session.get(url, timeout=10)
                        _json = await res.json()
                        break
                except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                    if (time.perf_counter() - start) > self._timeout:
                        raise asyncio.TimeoutError(
                            f"Couldn't connect to chrome within {self._timeout} seconds")
            self._socket = await SingleCDPSocket(websock_url=_json["webSocketDebuggerUrl"], timeout=self._timeout,
                                                 loop=self._loop, max_size=self._max_ws_size)
            self._started = True
        return self

    async def close(self) -> None:
        try:
            await self._socket.close()
        except websockets.ConnectionClosedError:
            pass
        except CDPError as e:
            if e.code == -32000 and e.message == 'Command can only be executed on top-level targets':
                pass
            else:
                raise e

    async def wait_for_cdp(self, event: str, timeout: float or None = None):
        """wait for an event
        see :func:`Target.wait_for_cdp <selenium_driverless.types.target.Target.wait_for_cdp>` for reference
        """
        if not self.socket:
            await self._init()
        return await self.socket.wait_for(event, timeout=timeout)

    async def add_cdp_listener(self, event: str, callback: typing.Callable[[dict], any]):
        """
        add a listener for a CDP event
        see :func:`Target.add_cdp_listener <selenium_driverless.types.target.Target.add_cdp_listener>` for reference
        """
        if not self.socket:
            await self._init()
        self.socket.add_listener(method=event, callback=callback)

    async def remove_cdp_listener(self, event: str, callback: typing.Callable[[dict], any]):
        """
        remove a listener for a CDP event
        see :func:`Target.remove_cdp_listener <selenium_driverless.types.target.Target.remove_cdp_listener>` for reference
        """
        if not self.socket:
            await self._init()
        self.socket.remove_listener(method=event, callback=callback)

    async def get_cdp_event_iter(self, event: str) -> typing.AsyncIterable[dict]:
        """
        iterate over CDP events on the current target
        see :func:`Target.get_cdp_event_iter <selenium_driverless.types.target.Target.get_cdp_event_iter>` for reference
        """
        if not self.socket:
            await self._init()
        return self.socket.method_iterator(method=event)

    async def execute_cdp_cmd(self, cmd: str, cmd_args: dict or None = None,
                              timeout: float or None = 10) -> dict:
        """Execute Chrome Devtools Protocol command and get returned result
        see :func:`Target.execute_cdp_cmd <selenium_driverless.types.target.Target.execute_cdp_cmd>` for reference
        """
        if not self.socket:
            await self._init()
        if cmd == "Browser.setDownloadBehavior":
            path = cmd_args.get("downloadPath")
            if path:
                self._downloads_paths[cmd_args.get("browserContextId", "DEFAULT")] = path
        result = await self.socket.exec(method=cmd, params=cmd_args, timeout=timeout)
        return result

    def downloads_dir_for_context(self, context_id: str = "DEFAULT") -> str:
        """get the default download directory for a specific context

        :param context_id: the id of the context to get the directory for
        """
        return self._downloads_paths.get(context_id)
