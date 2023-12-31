import asyncio
import inspect

from selenium_driverless.types.webelement import WebElement as AsyncWebElement


class WebElement(AsyncWebElement):
    def __init__(self, target, isolated_exec_id: int or None, frame_id: int or None, obj_id=None,
                 node_id=None, backend_node_id: str = None, loop=None, class_name: str = None,
                 context_id: int = None):
        if not loop:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        self._loop = loop
        super().__init__(target=target, obj_id=obj_id, node_id=node_id, loop=self._loop, context_id=context_id,
                         class_name=class_name, backend_node_id=backend_node_id,
                         isolated_exec_id=isolated_exec_id, frame_id=frame_id)
        self.__enter__()

    @property
    def class_name(self):
        return self._class_name

    def __enter__(self):
        return self.__aenter__

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
