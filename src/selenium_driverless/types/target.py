# io
import asyncio
import time
import typing
import warnings
from base64 import b64decode
import aiofiles
from typing import List

import websockets
from cdp_socket.exceptions import CDPError
from cdp_socket.socket import SingleCDPSocket

# pointer
from selenium_driverless.sync.pointer import Pointer as SyncPointer
from selenium_driverless.input.pointer import Pointer
# other
from selenium_driverless.scripts.driver_utils import get_targets, get_target, get_cookies, get_cookie, delete_cookie, \
    delete_all_cookies, add_cookie
from selenium_driverless.types.deserialize import StaleJSRemoteObjReference
from selenium_driverless.types.webelement import StaleElementReferenceException, NoSuchElementException
from selenium_driverless.sync.alert import Alert as SyncAlert
# Alert
from selenium_driverless.types.alert import Alert
from selenium_driverless.types.webelement import WebElement
from selenium_driverless.sync.webelement import WebElement as SyncWebElement


class NoSuchIframe(Exception):
    def __init__(self, elem: WebElement, message: str):
        self._elem = elem
        super().__init__(message)

    @property
    def elem(self):
        return self._elem


class Target:
    """Allows you to drive the browser without chromedriver."""

    # noinspection PyShadowingBuiltins
    def __init__(self, host: str, target_id: str, driver, is_remote: bool = False,
                 loop: asyncio.AbstractEventLoop or None = None, timeout: float = 30,
                 type: str = None, start_socket: bool = False, max_ws_size: int = 2 ** 20) -> None:
        """Creates a new instance of the chrome target. Starts the service and
        then creates new instance of chrome target.

        :Args:
         - options - this takes an instance of ChromeOptions.rst
        """
        self._base_target = None
        self._parent_target = None
        self._window_id = None
        self._pointer = None
        self._page_enabled = None
        self._dom_enabled = None
        self._max_ws_size = max_ws_size

        self._global_this_ = {}
        self._document_elem_ = None
        self._alert = None

        self._targets: list = []
        self._socket = None
        self._isolated_context_id_ = None
        self._exec_context_id_ = ""
        self._targets: typing.Dict[str, Target] = {}

        self._is_remote = is_remote
        self._host = host
        self._id = target_id
        self._context_id = None
        self._type = type
        self._timeout = timeout

        self._loop = loop
        self._start_socket = start_socket
        self._on_closed_ = []

        self._driver = driver

    def __repr__(self):
        return f'<{type(self).__module__}.{type(self).__name__} (target_id="{self.id}", host="{self._host}")>'

    @property
    def id(self):
        return self._id

    @property
    async def browser_context_id(self):
        if not self._context_id:
            info = await self.info
            return info.browser_context_id
        return self._context_id

    @property
    def base_target(self):
        return self._base_target

    @property
    def socket(self) -> SingleCDPSocket:
        return self._socket

    def __eq__(self, other):
        if isinstance(other, Target):
            return other.socket == self.socket
        return False

    def __enter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    async def __aenter__(self):
        # doesn't do anything (start_socket=False)
        return self

    def __await__(self):
        if self._start_socket:
            return self._init().__await__()
        else:
            # doesn't do anything (start_socket=False)
            return self.__aenter__().__await__()

    async def _init(self):
        if not self._socket:
            self._socket = await SingleCDPSocket(websock_url=f'ws://{self._host}/devtools/page/{self._id}',
                                                 timeout=self._timeout, loop=self._loop, max_size=self._max_ws_size)
            if self._loop:
                self._pointer = SyncPointer(target=self, loop=self._loop)
            else:
                self._pointer = Pointer(target=self)

            def set_alert(alert):
                self._alert = alert

            # noinspection PyUnusedLocal
            def remove_alert(alert):
                self._alert = None

            await self.add_cdp_listener("Page.javascriptDialogOpening", set_alert)
            await self.add_cdp_listener("Page.javascriptDialogClosed", remove_alert)
            await self.add_cdp_listener("Page.loadEventFired", self._on_loaded)
            await self.add_cdp_listener("Page.windowOpen", self._on_loaded)
            self.socket.on_closed.extend(self._on_closed)
        return self

    @property
    def _on_closed(self):
        if self.socket:
            return self.socket.on_closed
        else:
            return self._on_closed_

    # noinspection PyUnusedLocals,PyUnusedLocal
    async def _on_loaded(self, *args, **kwargs):
        self._global_this_ = {}
        self._document_elem_ = None
        self._isolated_context_id_ = None
        self._exec_context_id_ = None

    async def get_alert(self, timeout: float = 5):
        if not self._page_enabled:
            await self.execute_cdp_cmd("Page.enable", timeout=timeout)
        if self._loop:
            alert = SyncAlert(self, loop=self._loop, timeout=timeout)
        else:
            alert = await Alert(self, timeout=timeout)
        return alert

    async def get_targets_for_iframes(self, iframes: typing.List[WebElement]):
        if not iframes:
            raise ValueError(f"Expected WebElements, but got{iframes}")

        async def target_getter(target_id: str, timeout: float = 2, max_ws_size: int = 2 ** 20):
            return await get_target(target_id=target_id, host=self._host, loop=self._loop, is_remote=self._is_remote,
                                    timeout=timeout, max_ws_size=max_ws_size, driver=self._driver)

        _targets = await get_targets(cdp_exec=self.execute_cdp_cmd, target_getter=target_getter,
                                     _type="iframe", context_id=self._context_id, max_ws_size=self._max_ws_size)
        targets = {}

        for targetinfo in list(_targets.values()):
            # iterate over iframes
            target = targetinfo.Target
            base_frame = await target.base_frame

            #  check if iframe element is within iframes to search
            for iframe in iframes:
                tag_name = await iframe.tag_name
                if tag_name.upper() != "IFRAME":
                    raise NoSuchIframe(iframe, "element isn't a iframe")
                await iframe.obj_id
                iframe_frame_id = await iframe.__frame_id__
                if base_frame["id"] == iframe_frame_id:
                    if await self.type == "iframe":
                        target._parent_target = self
                    else:
                        target._base_target = self
                    targets[target.id] = target
        return list(targets.values())

    async def get_target_for_iframe(self, iframe: WebElement):
        targets = await self.get_targets_for_iframes([iframe])
        if not targets:
            raise NoSuchIframe(iframe, "no target for iframe found")
        return targets[0]

    # noinspection PyUnboundLocalVariable,PyProtectedMember
    async def get(self, url: str, referrer: str = None, wait_load: bool = True, timeout: float = 30) -> None:
        """Loads a web page in the current browser session."""
        if url == "about:blank":
            wait_load = False

        if "#" in url:
            # thanks to https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/139#issuecomment-1877197974
            current_url_base = (await self.current_url).split("#")[0]
            if url[0] == "#":
                # allow to navigate only by fragment ID of the current url
                url = current_url_base + url
                wait_load = False
            elif url.split("#")[0] == current_url_base:
                wait_load = False

        if wait_load:
            if not self._page_enabled:
                await self.execute_cdp_cmd("Page.enable")
            wait = asyncio.create_task(self.wait_for_cdp("Page.loadEventFired", timeout=timeout))
        args = {"url": url, "transitionType": "link"}
        if referrer:
            args["referrer"] = referrer
        get = asyncio.create_task(self.execute_cdp_cmd("Page.navigate", args, timeout=timeout))
        if wait_load:
            try:
                await wait
            except (asyncio.TimeoutError, TimeoutError):
                raise TimeoutError(f'page: "{url}" didn\'t load within timeout of {timeout}')
        await get
        await self._on_loaded()

    async def _global_this(self, context_id: str = None):
        if not context_id:
            context_id = self._exec_context_id_
        if (not self._global_this_.get(context_id)) or self._loop:
            from selenium_driverless.types.deserialize import JSRemoteObj
            from selenium_driverless.types import JSEvalException
            args = {"expression": "globalThis",
                    "serializationOptions": {
                        "serialization": "idOnly"}}
            if context_id:
                args["contextId"] = context_id
            res = await self.execute_cdp_cmd("Runtime.evaluate", args)
            if "exceptionDetails" in res.keys():
                raise JSEvalException(res["exceptionDetails"])
            obj_id = res["result"]['objectId']

            base_frame = await self.base_frame
            # target can have no frames at all
            frame_id = None
            if base_frame:
                frame_id = base_frame.get("id")

            # noinspection PyUnresolvedReferences
            obj = JSRemoteObj(obj_id=obj_id, target=self, isolated_exec_id=None,
                              frame_id=frame_id)
            if not context_id:
                context_id = obj.__context_id__
                self._exec_context_id_ = context_id
            self._global_this_[context_id] = obj
        return self._global_this_[context_id]

    @property
    async def _isolated_context_id(self) -> int:
        doc = await self._document_elem
        return await doc.__isolated_exec_id__

    @property
    def pointer(self) -> Pointer:
        return self._pointer

    async def execute_raw_script(self, script: str, *args, await_res: bool = False, serialization: str = None,
                                 max_depth: int = None, timeout: float = 2, execution_context_id: str = None,
                                 unique_context: bool = False):
        """executes a JavaScript on ``GlobalThis`` such as

        .. code-block:: js

            function(...arguments){return document}

        ``this`` and ``obj`` refers to ``globalThis`` (=> window) here

        :param script: the script as a string
        :param args: the argument which are passed to the function. Those can be either json-serializable or a RemoteObject such as WebELement
        :param await_res: whether to await the function or the return value of it
        :param serialization: can be one of ``deep``, ``json``, ``idOnly``
        :param max_depth: The maximum depth objects get serialized.
        :param timeout: the maximum time to wait for the execution to complete
        :param execution_context_id: the execution context id to run the JavaScript in. Exclusive with unique_context
        :param unique_context: whether to use a isolated context to run the Script in.

        see `Runtime.callFunctionOn <https://chromedevtools.github.io/devtools-protocol/tot/Runtime/#method-callFunctionOn>`_
        """

        if execution_context_id and unique_context:
            warnings.warn("got execution_context_id and unique_context=True, defaulting to execution_context_id")
        if unique_context:
            execution_context_id = await self._isolated_context_id

        if timeout is None:
            timeout = 2

        globalthis = await self._global_this(execution_context_id)
        try:
            res = await globalthis.__exec_raw__(script, *args, await_res=await_res, serialization=serialization,
                                                max_depth=max_depth, timeout=timeout,
                                                execution_context_id=execution_context_id)
        except StaleJSRemoteObjReference:
            await self.wait_for_cdp("Page.loadEventFired", timeout)
            globalthis = await self._global_this(execution_context_id)
            res = await globalthis.__exec_raw__(script, *args, await_res=await_res, serialization=serialization,
                                                max_depth=max_depth, timeout=timeout,
                                                execution_context_id=execution_context_id)
        return res

    async def execute_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                             timeout: float = None, execution_context_id: str = None,
                             unique_context: bool = None):
        """executes JavaScript synchronously on ``GlobalThis`` such as

        .. code-block:: js

            return document

        ``this`` and ``obj`` refers to ``globalThis`` (=> window) here

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        if execution_context_id and unique_context:
            warnings.warn("got execution_context_id and unique_context=True, defaulting to execution_context_id")
        if unique_context:
            execution_context_id = await self._isolated_context_id
        if timeout is None:
            timeout = 2

        start = time.monotonic()
        while (time.monotonic() - start) < timeout:
            global_this = await self._global_this(execution_context_id)
            try:
                res = await global_this.__exec__(script, *args, serialization=serialization,
                                                 max_depth=max_depth, timeout=timeout,
                                                 execution_context_id=execution_context_id)
                return res
            except StaleJSRemoteObjReference:
                pass
        raise asyncio.TimeoutError("Couldn't execute script, possibly due to a reload loop")

    async def execute_async_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                                   timeout: float = None, execution_context_id: str = None,
                                   unique_context: bool = None):
        """executes JavaScript asynchronously on ``GlobalThis``

        .. code-block:: js

            resolve = arguments[arguments.length-1]

        ``this`` and ``obj`` refers to ``globalThis`` (=> window) here

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        if execution_context_id and unique_context:
            warnings.warn("got execution_context_id and unique_context=True, defaulting to execution_context_id")
        if unique_context:
            execution_context_id = await self._isolated_context_id
        if timeout is None:
            timeout = 2

        start = time.monotonic()
        while (time.monotonic() - start) < timeout:
            global_this = await self._global_this(execution_context_id)
            try:
                res = await global_this.__exec_async__(script, *args, serialization=serialization,
                                                       max_depth=max_depth, timeout=timeout,
                                                       execution_context_id=execution_context_id)
                return res
            except StaleJSRemoteObjReference:
                await asyncio.sleep(0)
        raise asyncio.TimeoutError("Couldn't execute script, possibly due to a reload loop")

    async def eval_async(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                         timeout: float = None, execution_context_id: str = None,
                         unique_context: bool = None):
        """executes JavaScript asynchronously on ``GlobalThis`` such as

        .. code-block:: js

            res = await fetch("https://httpbin.org/get");
            // mind CORS!
            json = await res.json()
            return json

        ``this`` refers to ``globalThis`` (=> window)

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        if execution_context_id and unique_context:
            warnings.warn("got execution_context_id and unique_context=True, defaulting to execution_context_id")
        if unique_context:
            execution_context_id = await self._isolated_context_id

        start = time.monotonic()
        while (time.monotonic() - start) < timeout:
            global_this = await self._global_this(execution_context_id)
            try:
                res = await global_this.__eval_async__(script, *args, serialization=serialization,
                                                       max_depth=max_depth, timeout=timeout,
                                                       execution_context_id=execution_context_id)
                return res
            except StaleJSRemoteObjReference:
                await asyncio.sleep(0)
        raise asyncio.TimeoutError("Couldn't execute script, possibly due to a reload loop")

    @property
    async def current_url(self) -> str:
        """Gets the URL of the current page.

        :Usage:
            ::

                target.current_url
        """
        target = await self.info
        return target.url

    @property
    async def page_source(self) -> str:
        """Gets the docs_source of the current page.

        :Usage:
            ::

                target.page_source
        """
        elem = await self._document_elem
        return await elem.source

    async def close(self, timeout: float = 2) -> None:
        """Closes the current window.

        :Usage:
            ::

                target.close()
        """
        try:
            await self.execute_cdp_cmd("Page.close", timeout=timeout)
            await self._socket.close()
        except websockets.ConnectionClosedError:
            pass
        except CDPError as e:
            if e.code == -32000 and e.message == 'Command can only be executed on top-level targets':
                pass
            else:
                raise e
        except (asyncio.TimeoutError, TimeoutError):
            pass

    async def focus(self):
        await self.execute_cdp_cmd("Target.activateTarget",
                                   {"targetId": self.id})
        try:
            await self.execute_cdp_cmd("Emulation.setFocusEmulationEnabled", {"enabled": True})
        except CDPError as e:
            if not (e.code == -32601 and e.message == "'Emulation.setFocusEmulationEnabled' wasn't found"):
                raise e

    @property
    async def info(self):
        res = await self.execute_cdp_cmd("Target.getTargetInfo", {"targetId": self.id})
        return await TargetInfo(res["targetInfo"], self)

    @property
    async def frame_tree(self):
        try:
            res = await self.execute_cdp_cmd("Page.getFrameTree")
            return res["frameTree"]
        except CDPError as e:
            if not (e.code == -32601 and e.message == "'Page.getFrameTree' wasn't found"):
                raise e

    @property
    async def base_frame(self):
        res = await self.frame_tree
        if res:
            return res["frame"]

    @property
    async def type(self):
        if not self._type:
            info = await self.info
            self._type = info.type
        return self._type

    @property
    async def title(self) -> str:
        # noinspection GrazieInspection
        """Returns the title of the target"""
        target = await self.info
        return target.title

    @property
    async def url(self) -> str:
        info = await self.info
        return info.url

    @property
    async def window_id(self):
        if not self._window_id:
            result = await self.execute_cdp_cmd("Browser.getWindowForTarget", {"targetId": self.id})
            self._window_id = result["windowId"]
        return self._window_id

    # noinspection PyUnusedLocal
    async def print_page(self) -> str:
        """Takes PDF of the current page.

        The target makes the best effort to return a PDF based on the
        provided parameters.

        returns Base64-encoded pdf data as a string
        """
        page = await self.execute_cdp_cmd("Page.printToPDF")
        return page["data"]

    @property
    async def _current_history_idx(self):
        res = await self.execute_cdp_cmd("Page.getNavigationHistory")
        return res["currentIndex"]

    # Navigation
    async def back(self) -> None:
        """Goes one step backward in the browser history.

        :Usage:
            ::

                target.back()
        """
        await self.execute_cdp_cmd("Page.navigateToHistoryEntry", {"entryId": await self._current_history_idx - 1})
        await self._on_loaded()

    async def forward(self) -> None:
        """Goes one step forward in the browser history.

        :Usage:
            ::

                target.forward()
        """
        await self.execute_cdp_cmd("Page.navigateToHistoryEntry", {"entryId": await self._current_history_idx + 1})
        await self._on_loaded()

    async def refresh(self) -> None:
        """Refreshes the current page.

        :Usage:
            ::

                target.refresh()
        """
        await self.execute_cdp_cmd("Page.reload")
        await self._on_loaded()

    # Options
    async def get_cookies(self) -> List[dict]:
        """Returns a set of dictionaries, corresponding to cookies visible in
        the current context.
        """
        return await get_cookies(self)

    async def get_cookie(self, name) -> typing.Optional[typing.Dict]:
        """Get a single cookie by name. Returns the cookie if found, None if
        not.
        """
        return await get_cookie(target=self, name=name)

    async def delete_cookie(self, name: str, url: str = None, domain: str = None, path: str = None) -> None:
        """Deletes a single cookie with the given name.
        """
        return await delete_cookie(target=self, url=url, name=name, domain=domain, path=path)

    async def delete_all_cookies(self) -> None:
        """Delete all cookies in the scope of the context.
        """
        return await delete_all_cookies(self)

    # noinspection GrazieInspection
    async def add_cookie(self, cookie_dict) -> None:
        """Adds a cookie in the current (incognito-) context

        :param cookie_dict: see `Network.CookieParam <https://chromedevtools.github.io/devtools-protocol/tot/Network/#type-CookieParam>`__
        """
        if not (cookie_dict.get("url") or cookie_dict.get("domain") or cookie_dict.get("path")):
            cookie_dict["url"] = await self.current_url
        return await add_cookie(target=self, cookie_dict=cookie_dict)

    @property
    async def _document_elem(self) -> WebElement:
        if not self._document_elem_:
            res = await self.execute_cdp_cmd("DOM.getDocument", {"pierce": True})
            node_id = res["root"]["nodeId"]
            frame = await self.base_frame
            frame_id = frame["id"]
            if self._loop:
                self._document_elem_ = await SyncWebElement(target=self, node_id=node_id, loop=self._loop,
                                                            isolated_exec_id=None, frame_id=frame_id)
            else:
                self._document_elem_ = await WebElement(target=self, node_id=node_id, loop=self._loop,
                                                        isolated_exec_id=None, frame_id=frame_id)
        return self._document_elem_

    # noinspection PyUnusedLocal
    async def find_element(self, by: str, value: str, parent=None, timeout: int or None = None) -> WebElement:
        start = time.monotonic()
        elem = None
        while not elem:
            parent = await self._document_elem
            try:
                elem = await parent.find_element(by=by, value=value, timeout=None)
            except (StaleElementReferenceException, NoSuchElementException, StaleJSRemoteObjReference):
                await self._on_loaded()
            if (not timeout) or (time.monotonic() - start) > timeout:
                break
            await asyncio.sleep(0.01)
        if not elem:
            raise NoSuchElementException()
        return elem

    async def find_elements(self, by: str, value: str, parent=None) -> typing.List[WebElement]:
        if not parent:
            parent = await self._document_elem
        return await parent.find_elements(by=by, value=value)

    async def set_source(self, source: str, timeout: float = 15):
        start = time.monotonic()
        while (time.monotonic() - start) < timeout:
            try:
                document = await self._document_elem
                await document.set_source(source)
                return
            except StaleElementReferenceException:
                await self._on_loaded()
                await asyncio.sleep(0)
        raise TimeoutError("Couldn't get document element to not be stale")

    async def search_elements(self, query: str) -> typing.List[WebElement]:
        """
        query:str | Plain text or query selector or XPath search query.
        """
        # ensure DOM is enabled
        if not self._dom_enabled:
            await self.execute_cdp_cmd("DOM.enable")

        # ensure DOM.getDocument got called
        await self._document_elem

        elems = []
        res = await self.execute_cdp_cmd("DOM.performSearch",
                                         {"includeUserAgentShadowDOM": True, "query": query})
        search_id = res["searchId"]
        elem_count = res["resultCount"]
        if elem_count <= 0:
            return []

        res = await self.execute_cdp_cmd("DOM.getSearchResults",
                                         {"searchId": search_id, "fromIndex": 0, "toIndex": elem_count})
        for node_id in res["nodeIds"]:
            if self._loop:
                elem = await SyncWebElement(target=self, node_id=node_id, loop=self._loop, isolated_exec_id=None,
                                            frame_id=None)
            else:
                elem = await WebElement(target=self, node_id=node_id, loop=self._loop, isolated_exec_id=None,
                                        frame_id=None)
            elems.append(elem)
        return elems

    async def get_screenshot_as_file(self, filename) -> bool:
        # noinspection GrazieInspection
        """Saves a screenshot of the current window to a PNG image file.
                Returns False if there is any IOError, else returns True. Use full
                paths in your filename.

                :Args:
                 - filename: The full path you wish to save your screenshot to. This
                   should end with a `.png` extension.

                :Usage:
                    ::

                        target.get_screenshot_as_file('/Screenshots/foo.png')
                """
        if not str(filename).lower().endswith(".png"):
            warnings.warn(
                "name used for saved screenshot does not match file " "type. It should end with a `.png` extension",
                UserWarning,
            )
        png = await self.get_screenshot_as_png()
        try:
            async with aiofiles.open(filename, "wb") as f:
                await f.write(png)
        except OSError:
            return False
        finally:
            del png
        return True

    async def save_screenshot(self, filename) -> bool:
        # noinspection GrazieInspection
        """Saves a screenshot of the current window to a PNG image file.
                Returns False if there is any IOError, else returns True. Use full
                paths in your filename.

                :Args:
                 - filename: The full path you wish to save your screenshot to. This
                   should end with a `.png` extension.

                :Usage:
                    ::

                        target.save_screenshot('/Screenshots/foo.png')
                """
        return await self.get_screenshot_as_file(filename)

    async def get_screenshot_as_png(self) -> bytes:
        """Gets the screenshot of the current window as a binary data.

        :Usage:
            ::

                target.get_screenshot_as_png()
        """
        base_64 = await self.get_screenshot_as_base64()
        return b64decode(base_64.encode("ascii"))

    async def get_screenshot_as_base64(self) -> str:
        """Gets the screenshot of the current window as a base64 encoded string
        which is useful in embedded images in HTML.

        :Usage:
            ::

                target.get_screenshot_as_base64()
        """
        res = await self.execute_cdp_cmd("Page.captureScreenshot", {"format": "png"}, timeout=30)
        return res["data"]

    async def get_network_conditions(self):
        """Gets Chromium network emulation settings.

        :Returns:
            A dict. For example:
            {'latency': 4, 'download_throughput': 2, 'upload_throughput': 2,
            'offline': False}
        """
        raise NotImplementedError("not started with chromedriver")

    async def set_network_conditions(self, offline: bool, latency: int, download_throughput: int, upload_throughput: int,
                                     connection_type: typing.Literal[
                                         "none", "cellular2g", "cellular3g", "cellular4g", "bluetooth", "ethernet", "wifi", "wimax", "other"]) -> None:
        """Sets Chromium network emulation settings.

        :Args:
         - network_conditions: A dict with conditions specification.

        :Usage:
            ::

                target.set_network_conditions(
                    offline=False,
                    latency=5,  # additional latency (ms)
                    download_throughput=500 * 1024,  # maximal throughput
                    upload_throughput=500 * 1024,  # maximal throughput
                    connection_type="wifi")

            Note: 'throughput' can be used to set both (for download and upload).
        """
        args = {"offline": offline, "latency": latency,
                "downloadThroughput": download_throughput,
                "uploadThroughput": upload_throughput}

        conn_types = ["none", "cellular2g", "cellular3g", "cellular4g", "bluetooth", "ethernet", "wifi", "wimax",
                      "other"]
        if connection_type:
            if connection_type not in conn_types:
                raise ValueError(f"expected {conn_types} for connection_type,  but got {connection_type}")
            args["connectionType"] = connection_type

        await self.execute_cdp_cmd("Network.emulateNetworkConditions", args)

    async def delete_network_conditions(self) -> None:
        """Resets Chromium network emulation settings."""
        raise NotImplementedError("not started with chromedriver")

    async def wait_for_cdp(self, event: str, timeout: float or None = None):
        if not self.socket:
            await self._init()
        return await self.socket.wait_for(event, timeout=timeout)

    async def add_cdp_listener(self, event: str, callback: callable):
        if not self.socket:
            await self._init()
        self.socket.add_listener(method=event, callback=callback)

    async def remove_cdp_listener(self, event: str, callback: callable):
        if not self.socket:
            await self._init()
        self.socket.remove_listener(method=event, callback=callback)

    async def get_cdp_event_iter(self, event: str):
        if not self.socket:
            await self._init()
        return self.socket.method_iterator(method=event)

    async def execute_cdp_cmd(self, cmd: str, cmd_args: dict or None = None,
                              timeout: float or None = 10) -> dict:
        """Execute Chrome Devtools Protocol command and get returned result The
        command and command args should follow chrome devtools protocol
        domains/commands, refer to link
        https://chromedevtools.github.io/devtools-protocol/

        :Args:
         - cmd: A str, command name
         - cmd_args: A dict, command args. empty dict {} if there is no command args
        :Usage:
            ::

                target.execute_cdp_cmd('Network.getResponseBody', {'requestId': requestId})
        :Returns:
            A dict, empty dict {} if there is no result to return.
            For example to getResponseBody:
            {'base64Encoded': False, 'body': 'response body string'}
        """
        if not self.socket:
            await self._init()
        result = await self.socket.exec(method=cmd, params=cmd_args, timeout=timeout)
        if cmd == "Page.enable":
            self._page_enabled = True
        elif cmd == "Page.disable":
            self._page_enabled = False

        elif cmd == "DOM.enable":
            self._dom_enabled = True
        elif cmd == "DOM.disable":
            self._dom_enabled = False
        return result

    # noinspection PyTypeChecker
    async def get_sinks(self) -> list:
        """
        :Returns: A list of sinks available for Cast.
        """
        await self.execute_cdp_cmd("Cast.enable")
        raise NotImplementedError("not started with chromedriver")

    async def get_issue_message(self):
        """
        :Returns: An error message when there is any issue in a Cast session.
        """
        raise NotImplementedError("not started with chromedriver")

    async def set_sink_to_use(self, sink_name: str) -> dict:
        """Sets a specific sink, using its name, as a Cast session receiver
        target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        return await self.execute_cdp_cmd("Cast.setSinkToUse", {"sinkName": sink_name})

    async def start_desktop_mirroring(self, sink_name: str) -> dict:
        """Starts a desktop mirroring session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        return await self.execute_cdp_cmd("Cast.startDesktopMirrorin", {"sinkName": sink_name})

    async def start_tab_mirroring(self, sink_name: str) -> dict:
        """Starts a tab mirroring session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        return await self.execute_cdp_cmd("Cast.startTabMirroring", {"sinkName": sink_name})

    async def stop_casting(self, sink_name: str) -> dict:
        """Stops the existing Cast session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to stop the Cast session.
        """
        return await self.execute_cdp_cmd("Cast.stopCasting", {"sinkName": sink_name})


class TargetInfo:
    """
    Info for a Target

    .. note::

        the infos are not dynamic
    """

    def __init__(self, target_info: dict, target_getter: asyncio.Future or Target):
        self._id = target_info.get('targetId')
        self._type = target_info.get("type")
        self._title = target_info.get("title")
        self._url = target_info.get("url")
        self._attached = target_info.get("attached")
        self._opener_id = target_info.get("openerId")
        self._can_access_opener = target_info.get('canAccessOpener')
        self._opener_frame_id = target_info.get("openerFrameId")
        self._browser_context_id = target_info.get('browserContextId')
        self._subtype = target_info.get("subtype")

        self._target = target_getter
        self._started = False

    def __await__(self):
        return self._init().__await__()

    async def _init(self):
        if not self._started:
            self._started = True
        return self

    # noinspection PyPep8Naming
    @property
    def Target(self) -> Target:
        """
        the Target itself
        """
        return self._target

    @property
    def id(self) -> str:
        """the ``Target.TargetID``"""
        return self._id

    @property
    def type(self) -> str:
        return self._type

    @property
    def title(self) -> str:
        return self._title

    @property
    def url(self) -> str:
        return self._url

    @property
    def attached(self) -> str:
        """Whether the target has an attached client."""
        return self._attached

    @property
    def opener_id(self) -> str:
        """Opener ``Target.TargetId``"""
        return self._opener_id

    @property
    def can_access_opener(self):
        """Whether the target has access to the originating window."""
        return self._can_access_opener

    @property
    def opener_frame_id(self):
        """``Page.FrameId`` of originating window (is only set if target has an opener)."""
        return self._opener_frame_id

    @property
    def browser_context_id(self):
        """``Browser.BrowserContextID``"""
        return self._browser_context_id

    @property
    def subtype(self):
        """Provides additional details for specific target types. For example, for the type of "page", this may be set to "portal" or "prerender"""
        return self._subtype

    def __repr__(self):
        return f'{self.__class__.__name__}(type="{self.type}",title="{self.title})"'
