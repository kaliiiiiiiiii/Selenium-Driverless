import asyncio
import typing
import warnings
from base64 import b64decode
from typing import List
from typing import Optional
import websockets
import aiohttp

from cdp_socket.exceptions import CDPError
from cdp_socket.socket import SingleCDPSocket

from selenium.webdriver.common.print_page_options import PrintOptions

from selenium_driverless.input.pointer import Pointer
from selenium_driverless.sync.pointer import Pointer as SyncPointer

from selenium_driverless.sync.webelement import WebElement as SyncWebElement
from selenium_driverless.types.webelement import WebElement, RemoteObject

from selenium_driverless.types.alert import Alert
from selenium_driverless.sync.alert import Alert as SyncAlert

from selenium_driverless.scripts.driver_utils import get_targets, get_target, get_cookies, get_cookie, delete_cookie, \
    delete_all_cookies, add_cookie
from selenium_driverless.types.target import NoSuchIframe, TargetInfo, Target


class BaseTarget(Target):
    """Allows you to drive the browser without chromedriver."""

    # noinspection PyMissingConstructor
    def __init__(self, host: str, is_remote: bool = False,
                 loop: asyncio.AbstractEventLoop or None = None, timeout: float = 30) -> None:
        """Creates a new instance of the chrome target. Starts the service and
        then creates new instance of chrome target.

        :Args:
         - options - this takes an instance of ChromeOptions
        """
        self._base_target = None
        self._parent_target = None
        self._window_id = None
        self._pointer = None
        self._page_enabled = None
        self._dom_enabled = None

        self._global_this_ = None
        self._document_elem_ = None
        self._alert = None

        self._targets: list = []
        self._socket = None
        self._isolated_context_id_ = None
        self._targets: typing.Dict[str, Target] = {}

        self._is_remote = is_remote
        self._host = host
        self._id = "BaseTarget"
        self._context_id = None
        self._type = type
        self._timeout = timeout

        self._loop = loop
        self._started = False

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

    async def __aenter__(self):
        await self._init()
        return self

    def __enter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __await__(self):
        return self._init().__await__()

    async def _init(self):
        if not self._started:
            res = None
            while not res:
                try:
                    async with aiohttp.ClientSession() as session:
                        res = await session.get(f"http://{self._host}/json/version", timeout=self._timeout)
                        _json = await res.json()
                except aiohttp.ClientError:
                    pass
            self._socket = await SingleCDPSocket(websock_url=_json["webSocketDebuggerUrl"], timeout=self._timeout, loop=self._loop)
            self._global_this_ = await RemoteObject(target=self, js="globalThis", check_existence=False)
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
            self._started = True
        return self

    # noinspection PyUnusedLocal
    async def _on_loaded(self, *args, clear_context_id=False, **kwargs):
        self._global_this_ = None
        self._document_elem_ = None
        if clear_context_id:
            self._isolated_context_id_ = None

    async def get_alert(self, timeout: float = 5):
        if not self._page_enabled:
            await self.execute_cdp_cmd("Page.enable", timeout=timeout)
        if self._loop:
            alert = SyncAlert(self, loop=self._loop, timeout=timeout)
        else:
            alert = await Alert(self, timeout=timeout)
        return alert

    async def get_elem_for_frame(self, frame_id, frame_target, context_id: str = None,
                                 unique_context: bool = True):
        await frame_target.execute_cdp_cmd("DOM.enable")
        # noinspection PyProtectedMember
        await frame_target._document_elem
        res = await frame_target.execute_cdp_cmd("DOM.getFrameOwner",
                                                 {"frameId": frame_id})
        return await WebElement(self, node_id=res['nodeId'],
                                context_id=context_id, unique_context=unique_context)

    async def get_targets_for_iframes(self, iframes: typing.List[WebElement]):
        async def target_getter(target_id: str, timeout: float = 2):
            return await get_target(target_id=target_id, host=self._host, loop=self._loop, is_remote=self._is_remote,
                                    timeout=timeout)

        _targets = await get_targets(cdp_exec=self.execute_cdp_cmd, target_getter=target_getter,
                                     _type="iframe", context_id=self._context_id)

        context_id = iframes[0].context_id
        # noinspection PyProtectedMember
        unique_context = iframes[0]._unique_context
        targets = []

        for targetinfo in list(_targets.values()):
            # iterate over iframes
            target = targetinfo.Target
            base_frame = await target.base_frame
            elem = await self.get_elem_for_frame(frame_id=base_frame["id"], frame_target=self,
                                                 context_id=context_id, unique_context=unique_context)

            #  check if iframe element is within iframes to search
            for iframe in iframes:
                tag_name = await iframe.tag_name
                if tag_name.upper() != "IFRAME":
                    raise NoSuchIframe(iframe, "element isn't a iframe")
                if elem == iframe:
                    if await self.type == "iframe":
                        target._parent_target = self
                    else:
                        target._base_target = self
                    targets.append(target)
        return targets

    async def get_target_for_iframe(self, iframe: WebElement):
        targets = await self.get_targets_for_iframes([iframe])
        if not targets:
            raise NoSuchIframe(iframe, "no target for iframe found")
        return targets[0]

    # noinspection PyUnboundLocalVariable
    async def get(self, url: str, referrer: str = None, wait_load: bool = True, timeout: float = 30) -> None:
        """Loads a web page in the current browser session."""
        if url == "about:blank":
            wait_load = False
        if wait_load:
            if not self._page_enabled:
                await self.execute_cdp_cmd("Page.enable")
            wait = asyncio.create_task(self.wait_for_cdp("Page.loadEventFired", timeout=timeout))
        args = {"url": url, "transitionType": "link"}
        if referrer:
            args["referrer"] = referrer
        get = asyncio.create_task(self.execute_cdp_cmd("Page.navigate", args))
        if wait_load:
            try:
                await wait
            except asyncio.TimeoutError:
                raise TimeoutError(f"page didn't load within timeout of {timeout}")
        await get
        await self._on_loaded()

    async def _parse_res(self, res):
        if "subtype" in res.keys():
            if res["subtype"] == 'node':
                res["value"] = await WebElement(target=self, obj_id=res["objectId"],
                                                check_existence=False)
        if 'className' in res.keys():
            class_name = res['className']
            if class_name in ['NodeList', 'HTMLCollection']:
                elems = []
                obj = await RemoteObject(target=self, obj_id=res["objectId"], check_existence=False)
                for idx in range(int(res['description'][-2])):
                    elems.append(await obj.execute_script("return this[arguments[0]]", idx, serialization="deep"))
                res["value"] = elems
            elif class_name == 'XPathResult':
                elems = []
                obj = await RemoteObject(target=self, obj_id=res["objectId"], check_existence=False)
                if await obj.execute_script("return [7].includes(obj.resultType)", serialization="json"):
                    for idx in range(await obj.execute_script("return obj.snapshotLength", serialization="json")):
                        elems.append(await obj.execute_script("return obj.snapshotItem(arguments[0])", idx,
                                                              serialization="deep"))
                    res["value"] = elems
        return res

    @property
    async def _global_this(self):
        if (not self._global_this_) or self._loop:
            self._global_this_ = await RemoteObject(target=self, js="globalThis", check_existence=False)
        return self._global_this_

    @property
    async def _isolated_context_id(self) -> int:
        if (not self._isolated_context_id_) or self._loop:
            frame = await self.base_frame
            res = await self.execute_cdp_cmd("Page.createIsolatedWorld",
                                             {"frameId": frame["id"], "grantUniveralAccess": True,
                                              "worldName": "You got here hehe:)"})
            self._isolated_context_id_ = res["executionContextId"]
        return self._isolated_context_id_

    @property
    def pointer(self) -> Pointer:
        return self._pointer

    async def execute_raw_script(self, script: str, *args, await_res: bool = False, serialization: str = None,
                                 max_depth: int = None, timeout: float = 2, obj_id: str = None,
                                 execution_context_id: str = None, unique_context: bool = False):
        """
        example:
        script= "function(...arguments){obj.click()}"
        "const obj" will be the Object according to obj_id
        this is by default globalThis (=> window)
        """
        from selenium_driverless.types import RemoteObject, JSEvalException

        if not args:
            args = []
        if not serialization:
            serialization = "deep"

        _args = []
        base_id = None
        for arg in args:
            if isinstance(arg, RemoteObject):
                _args.append({"objectId": await arg.obj_id})
                exec_id = arg.context_id
                if not exec_id:
                    # noinspection PyProtectedMember
                    base_id = arg._base_obj
                if execution_context_id and exec_id != execution_context_id:
                    raise ValueError("got multiple arguments with different execution-context-id's")
                execution_context_id = exec_id
            else:
                _args.append({"value": arg})

        if not (obj_id or execution_context_id):
            if unique_context:
                execution_context_id = await self._isolated_context_id
            else:
                if base_id:
                    obj_id = base_id
                else:
                    global_this = await self._global_this
                    obj_id = await global_this.obj_id

        ser_opts = {"serialization": serialization, "maxDepth": max_depth,
                    "additionalParameters": {"includeShadowTree": "all", "maxNodeDepth": max_depth}}
        args = {"functionDeclaration": script,
                "arguments": _args, "userGesture": True, "awaitPromise": await_res, "serializationOptions": ser_opts}

        if execution_context_id and obj_id:
            raise ValueError("execution_context_id and obj_id can't be specified at the same time")
        if obj_id:
            args["objectId"] = obj_id
        if execution_context_id:
            args["executionContextId"] = execution_context_id

        res = await self.execute_cdp_cmd("Runtime.callFunctionOn", args, timeout=timeout)
        if "exceptionDetails" in res.keys():
            raise JSEvalException(res["exceptionDetails"])
        res = res["result"]
        res = await self._parse_res(res)
        return res

    async def execute_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                             timeout: float = None, only_value=True, obj_id=None, execution_context_id: str = None,
                             unique_context: bool = None):
        """
        exaple: script = "return elem.click()"
        """
        from selenium_driverless.types import RemoteObject
        for arg in args:
            if isinstance(arg, RemoteObject):
                execution_context_id = arg.context_id

        if execution_context_id and obj_id:
            obj = RemoteObject(obj_id=obj_id, target=self, check_existence=False,
                               context_id=execution_context_id, unique_context=unique_context)
            args = [obj, *args]
            obj_id = None
            script = """
                (function(...arguments){
                    const obj = arguments[0]
                    arguments = arguments[1:]
                    """ + script + "})"
        else:
            script = """
                        (function(...arguments){
                            const obj = this   
                            """ + script + "})"
        res = await self.execute_raw_script(script, *args, max_depth=max_depth,
                                            serialization=serialization, timeout=timeout,
                                            await_res=False, obj_id=obj_id, unique_context=unique_context,
                                            execution_context_id=execution_context_id)
        if only_value:
            if "value" in res.keys():
                return res["value"]
        else:
            return res

    async def execute_async_script(self, script: str, *args, max_depth: int = 2,
                                   serialization: str = None, timeout: float = 2,
                                   only_value=True, obj_id=None, execution_context_id: str = None,
                                   unique_context: bool = False):
        from selenium_driverless.types import RemoteObject
        for arg in args:
            if isinstance(arg, RemoteObject):
                execution_context_id = arg.context_id
        if execution_context_id and obj_id:
            obj = RemoteObject(obj_id=obj_id, target=self, check_existence=False,
                               context_id=execution_context_id, unique_context=unique_context)
            args = [obj, *args]
            obj_id = None
            script = """
                (function(...arguments){
                    const obj = arguments[0]
                    arguments = arguments[1:]
                    const promise = new Promise((resolve, reject) => {
                                          arguments.push(resolve)
                        });""" + script + ";return promise})"
        else:
            script = """(function(...arguments){
                                   const obj = this
                                   const promise = new Promise((resolve, reject) => {
                                          arguments.push(resolve)
                                    });""" + script + ";return promise})"
        res = await self.execute_raw_script(script, *args, max_depth=max_depth,
                                            serialization=serialization, timeout=timeout,
                                            await_res=True, obj_id=obj_id,
                                            execution_context_id=execution_context_id, unique_context=unique_context)
        if only_value:
            if "value" in res.keys():
                return res["value"]
        else:
            return res

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
        """Gets the source of the current page.

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
            await self._socket.close()
        except websockets.ConnectionClosedError:
            pass
        except CDPError as e:
            if e.code == -32000 and e.message == 'Command can only be executed on top-level targets':
                pass
            else:
                raise e

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
        res = await self.execute_cdp_cmd("Page.getFrameTree")
        return res["frameTree"]

    @property
    async def base_frame(self):
        res = await self.frame_tree
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
    async def print_page(self, print_options: Optional[PrintOptions] = None) -> str:
        """Takes PDF of the current page.

        The target makes the best effort to return a PDF based on the
        provided parameters.
        """
        options = {}
        if print_options:
            options = print_options.to_dict()
            raise NotImplementedError("Options not yet supported")

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
        """Adds a cookie to your current session.

        :Args:
         - cookie_dict: A dictionary object, with required keys - "name" and "value";
            optional keys - "path", "domain", "secure", "httpOnly", "expiry", "sameSite"

        :Usage:
            ::

                target.add_cookie({'name' : 'foo', 'value' : 'bar'})
                target.add_cookie({'name' : 'foo', 'value' : 'bar', 'path' : '/'})
                target.add_cookie({'name' : 'foo', 'value' : 'bar', 'path' : '/', 'secure' : True})
                target.add_cookie({'name' : 'foo', 'value' : 'bar', 'sameSite' : 'Strict'})
        """
        return await add_cookie(target=self, cookie_dict=cookie_dict, context_id=await self.browser_context_id)

    @property
    async def _document_elem(self) -> WebElement:
        if (not self._document_elem_) or self._loop:
            res = await self.execute_cdp_cmd("DOM.getDocument", {"pierce": True})
            node_id = res["root"]["nodeId"]
            self._document_elem_ = await WebElement(target=self, node_id=node_id, check_existence=False,
                                                    loop=self._loop, unique_context=True)
        return self._document_elem_

    # noinspection PyUnusedLocal
    async def find_element(self, by: str, value: str, parent=None):
        if not parent:
            parent = await self._document_elem
        return await parent.find_element(by=by, value=value)

    async def find_elements(self, by: str, value: str, parent=None):
        if not parent:
            parent = await self._document_elem
        return await parent.find_elements(by=by, value=value)

    async def search_elements(self, query: str):
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
                elem = await SyncWebElement(target=self, check_existence=False, node_id=node_id, loop=self._loop)
            else:
                elem = await WebElement(target=self, check_existence=False, node_id=node_id, loop=self._loop)
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
            with open(filename, "wb") as f:
                f.write(png)
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
        res = await self.execute_cdp_cmd("Page.captureScreenshot", {"format": "png"})
        return res["data"]

    async def get_network_conditions(self):
        """Gets Chromium network emulation settings.

        :Returns:
            A dict. For example:
            {'latency': 4, 'download_throughput': 2, 'upload_throughput': 2,
            'offline': False}
        """
        raise NotImplementedError("not started with chromedriver")

    async def set_network_conditions(self, offline: bool, latency: int, download_throughput: int,
                                     upload_throughput: int, connection_type: None) -> None:
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
