import asyncio
from selenium_driverless.types.context import Context as AsyncContext
from selenium_driverless.types.target import Target
import inspect


class Context(AsyncContext):
    def __init__(self, base_target: Target, context_id: str = None, loop: asyncio.AbstractEventLoop = None) -> None:
        if not loop:
            loop = asyncio.new_event_loop()
        super().__init__(base_target=base_target, context_id=context_id, loop=loop)

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
