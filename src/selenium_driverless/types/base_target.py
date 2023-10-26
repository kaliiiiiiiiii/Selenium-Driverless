import asyncio

import aiohttp
import websockets
from cdp_socket.exceptions import CDPError
from cdp_socket.socket import SingleCDPSocket


class BaseTarget:
    """Allows you to drive the browser without chromedriver."""

    # noinspection PyMissingConstructor
    def __init__(self, host: str, is_remote: bool = False,
                 loop: asyncio.AbstractEventLoop or None = None, timeout: float = 30, max_ws_size:int=2**20) -> None:
        """Creates a new instance of the chrome target. Starts the service and
        then creates new instance of chrome target.

        :Args:
         - options - this takes an instance of ChromeOptions
        """
        self._socket = None

        self._is_remote = is_remote
        self._host = host
        self._id = "BaseTarget"

        self._loop = loop
        self._started = False
        self._timeout = timeout
        self._max_ws_size = max_ws_size

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
            res = None
            while not res:
                try:
                    async with aiohttp.ClientSession() as session:
                        res = await session.get(f"http://{self._host}/json/version", timeout=self._timeout)
                        _json = await res.json()
                except aiohttp.ClientError:
                    pass
            self._socket = await SingleCDPSocket(websock_url=_json["webSocketDebuggerUrl"], timeout=self._timeout,
                                                 loop=self._loop, max_size=self._max_ws_size)
            self._started = True
        return self

    async def close(self) -> None:
        """Closes the current window.

        :Usage:
            ::

                target.close()
        """
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
        if not self.socket:
            await self._init()
        return await self.socket.wait_for(event, timeout=timeout)

    async def add_cdp_listener(self, event: str, callback: callable):
        if not self.socket:
            await self._init()
        self.socket.add_listener(method=event, callback=callback)

    async def remove_cdp_listener(self, event: str, callback: callable):
        if not self.socket:
            await self._init()
        self.socket.remove_listener(method=event, callback=callback)

    async def get_cdp_event_iter(self, event: str):
        if not self.socket:
            await self._init()
        return self.socket.method_iterator(method=event)

    async def execute_cdp_cmd(self, cmd: str, cmd_args: dict or None = None,
                              timeout: float or None = 10) -> dict:
        """Execute Chrome Devtools Protocol command and get returned result The
        command and command args should follow chrome devtools protocol
        domains/commands, refer to link
        https://chromedevtools.github.io/devtools-protocol/

        :Args:
         - cmd: A str, command name
         - cmd_args: A dict, command args. empty dict {} if there is no command args
        :Usage:
            ::

                target.execute_cdp_cmd('Network.getResponseBody', {'requestId': requestId})
        :Returns:
            A dict, empty dict {} if there is no result to return.
            For example to getResponseBody:
            {'base64Encoded': False, 'body': 'response body string'}
        """
        if not self.socket:
            await self._init()
        result = await self.socket.exec(method=cmd, params=cmd_args, timeout=timeout)
        return result
