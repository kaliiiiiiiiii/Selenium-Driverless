import asyncio
import inspect

from selenium_driverless.input.pointer import Pointer as AsyncPointer, PointerType


class Pointer(AsyncPointer):
    def __init__(self, target, pointer_type: str = PointerType.MOUSE, loop: asyncio.AbstractEventLoop = None):
        super().__init__(target=target, pointer_type=pointer_type)
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
