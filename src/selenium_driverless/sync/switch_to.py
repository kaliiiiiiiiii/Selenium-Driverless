import asyncio
import inspect

from selenium_driverless.scripts.switch_to import SwitchTo as AsyncSwitchTo


class SwitchTo(AsyncSwitchTo):
    def __init__(self, context, loop, context_id: str = None):
        super().__init__(context=context, context_id=context_id)
        if not loop:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self._loop = loop

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.__aexit__(*args, **kwargs)

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
