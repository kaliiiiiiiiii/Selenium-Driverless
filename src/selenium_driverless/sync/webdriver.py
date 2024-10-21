import asyncio
import inspect

from selenium_driverless.types.options import Options as ChromeOptions
from selenium_driverless.webdriver import Chrome as AsyncDriver


class Chrome(AsyncDriver):
    def __init__(self, options: ChromeOptions = None, loop: asyncio.AbstractEventLoop = None,
                 debug=False, max_ws_size: int = 2 ** 20):
        super().__init__(options=options, debug=debug, max_ws_size=max_ws_size)
        if not loop:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self._loop = loop
        self.start_session()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.__aexit__(*args, **kwargs)

    async def quit(self, timeout: float = 30, clean_dirs: bool = True):
        await super().quit(timeout=timeout, clean_dirs=clean_dirs)

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
