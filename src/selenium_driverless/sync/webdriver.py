from selenium_driverless.scripts.options import Options as ChromeOptions
import asyncio
from selenium_driverless.webdriver import Chrome as AsyncDriver
import inspect


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
    
    def quit(self):
        try:
            asyncio.get_running_loop()
            return super().quit()
        except RuntimeError:
            return self._loop.run_until_complete(super().quit())

    @property
    async def _document_node_id(self):
        # because events don't seem to work
        res = await self.execute_cdp_cmd("DOM.getDocument", {"pierce": True})
        self._document_node_id_ = res["root"]["nodeId"]
        return self._document_node_id_

    async def execute_raw_script(self, script: str, *args, await_res: bool = False, serialization: str = None,
                                 max_depth: int = None, timeout: int = 2, obj_id=None, warn: bool = False):
        # because events don't seem to work
        self._global_this = None
        return await super().execute_raw_script(script, *args, await_res=await_res, serialization=serialization,
                                                max_depth=max_depth, timeout=timeout, obj_id=obj_id, warn=warn)

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
