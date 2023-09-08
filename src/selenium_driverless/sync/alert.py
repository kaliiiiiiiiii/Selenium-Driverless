import asyncio
import inspect

from selenium_driverless.types.alert import Alert as AsyncAlert


class Alert(AsyncAlert):
    def __init__(self, target, loop, timeout: float = 5):
        if not loop:
            loop = asyncio.new_event_loop()
        self._loop = loop
        super().__init__(target=target, timeout=timeout)
        self._init()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.__aexit__(*args, **kwargs)

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
