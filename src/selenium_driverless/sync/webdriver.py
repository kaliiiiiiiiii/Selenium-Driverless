from selenium_driverless.scripts.options import Options as ChromeOptions
import asyncio
from selenium_driverless.webdriver import Chrome as AsyncDriver
import inspect
from selenium_driverless.types.webelement import RemoteObject, WebElement


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
    async def _document_elem(self):
        # because events don't seem to work, see https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/43
        res = await self.execute_cdp_cmd("DOM.getDocument", {"pierce": True})
        node_id = res["root"]["nodeId"]
        self._document_elem_ = await WebElement(driver=self, node_id=node_id, check_existence=False,
                                                loop=self._loop)
        return await self._document_elem_

    @property
    async def _global_this(self):
        # because events don't seem to work, see https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/43
        self._global_this_ = await RemoteObject(driver=self, js="globalThis", check_existence=False)
        return self._global_this_

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
