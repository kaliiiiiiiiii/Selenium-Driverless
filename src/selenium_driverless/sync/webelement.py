import asyncio
import inspect

from selenium_driverless.types.webelement import WebElement as AsyncWebElement, RemoteObject


class WebElement(AsyncWebElement):
    def __init__(self, target, loop=None, js: str = None, obj_id=None, node_id=None, check_existence=True,
                 context_id: int = None, unique_context: bool = True):
        if not loop:
            loop = asyncio.new_event_loop()
        self._loop = loop
        super().__init__(target=target, js=js, obj_id=obj_id, node_id=node_id,
                         check_existence=check_existence, loop=self._loop, context_id=context_id,
                         unique_context=unique_context)
        self.__enter__()

    @property
    async def node_id(self):
        if not self._obj_id:
            await self.obj_id
            return self._node_id
        self._node_id = None
        return await super().node_id

    def __enter__(self):
        return self.__aenter__

    def __exit__(self, *args, **kwargs):
        self.__aexit__(*args, **kwargs)

    # noinspection PyProtectedMember
    def __eq__(self, other):
        if isinstance(other, RemoteObject):
            return self._obj_id == other._obj_id
        return False

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
