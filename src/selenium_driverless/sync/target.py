import asyncio
import inspect

from selenium_driverless.types.target import Target as AsyncTarget


class Target(AsyncTarget):
    # noinspection PyShadowingBuiltins
    def __init__(self, host: str, target_id: str, is_remote: bool = False,
                 loop: asyncio.AbstractEventLoop or None = None, timeout: float = 30,
                 type: str = None) -> None:
        super().__init__(host=host, target_id=target_id,
                         is_remote=is_remote, loop=loop,
                         timeout=timeout, type=type)
        if not loop:
            loop = asyncio.new_event_loop()
        self._loop = loop

    def __exit__(self, *args, **kwargs):
        return self.__aexit__(*args, **kwargs)

    def __getattribute__(self, item):
        item = super().__getattribute__(item)
        if item is None:
            return item
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            if inspect.iscoroutinefunction(item):
                def syncified(*args, **kwargs):
                    return self._loop.run_until_complete(item(*args, **kwargs))
                return syncified
            if inspect.isawaitable(item):
                return self._loop.run_until_complete(item)
        return item
