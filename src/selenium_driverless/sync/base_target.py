import asyncio
import inspect

from selenium_driverless.types.base_target import BaseTarget as AsyncBaseTarget


class BaseTarget(AsyncBaseTarget):
    # noinspection PyShadowingBuiltins
    def __init__(self, host: str, is_remote: bool = False,
                 loop: asyncio.AbstractEventLoop or None = None, timeout: float = 30,
                 max_ws_size: int = 2 ** 20) -> None:
        if not loop:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self._loop = loop
        super().__init__(host=host, is_remote=is_remote, loop=loop, timeout=timeout, max_ws_size=max_ws_size)

    def __exit__(self, *args, **kwargs):
        return self.__aexit__(*args, **kwargs)

    def __getattribute__(self, item):
        res = super().__getattribute__(item)
        if res is None or item == "_loop":
            return res
        loop = self._loop
        if loop and (not loop.is_running()):
            if inspect.iscoroutinefunction(res):
                def syncified(*args, **kwargs):
                    return self._loop.run_until_complete(res(*args, **kwargs))

                return syncified
            if inspect.isawaitable(res):
                return self._loop.run_until_complete(res)
        return res
