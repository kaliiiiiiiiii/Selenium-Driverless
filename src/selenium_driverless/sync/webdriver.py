import asyncio
import inspect

from selenium_driverless.types.options import Options as ChromeOptions
from selenium_driverless.webdriver import Chrome as AsyncDriver


class Chrome(AsyncDriver):
    def __init__(self, options: ChromeOptions = None, loop: asyncio.AbstractEventLoop = None):
        super().__init__(options=options)
        if not loop:
            loop = asyncio.new_event_loop()
        self._loop = loop
        self.start_session()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.__aexit__(*args, **kwargs)

    def quit(self, timeout: float = 30):
        try:
            asyncio.get_running_loop()
            return super().quit()
        except RuntimeError:
            return self._loop.run_until_complete(super().quit(timeout=timeout))

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
