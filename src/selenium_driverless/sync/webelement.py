from selenium_driverless.types.webelement import WebElement as AsyncWebElement
import asyncio
import inspect


class WebElement(AsyncWebElement):
    def __init__(self, driver, loop=None, js: str = None, obj_id=None, parent=None, check_existence=True):
        super().__init__(driver=driver, js=js, obj_id=obj_id, parent=parent, check_existence=check_existence)
        if not loop:
            loop = asyncio.new_event_loop()
        self._loop = loop

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
