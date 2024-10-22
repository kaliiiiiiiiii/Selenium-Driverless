# io
import asyncio
import base64
import json
import os.path
import time
import typing
from typing_extensions import TypedDict
import warnings
from base64 import b64decode
import aiofiles
from typing import List
import pathlib
import random

import websockets
from cdp_socket.exceptions import CDPError
from cdp_socket.socket import SingleCDPSocket

# pointer
from selenium_driverless.sync.pointer import Pointer as SyncPointer
from selenium_driverless.input.pointer import Pointer
# other
from selenium_driverless.scripts.driver_utils import get_targets, get_target, get_cookies, get_cookie, delete_cookie, \
    delete_all_cookies, add_cookie
from selenium_driverless.utils.utils import safe_wrap_fut
from selenium_driverless.types.deserialize import StaleJSRemoteObjReference
from selenium_driverless.types.webelement import StaleElementReferenceException, NoSuchElementException
from selenium_driverless.sync.alert import Alert as SyncAlert
# Alert
from selenium_driverless.types.alert import Alert
from selenium_driverless.types.webelement import WebElement
from selenium_driverless.sync.webelement import WebElement as SyncWebElement

KEY_MAPPING = {
    'a': ('KeyA', 65), 'b': ('KeyB', 66), 'c': ('KeyC', 67), 'd': ('KeyD', 68), 'e': ('KeyE', 69),
    'f': ('KeyF', 70), 'g': ('KeyG', 71), 'h': ('KeyH', 72), 'i': ('KeyI', 73), 'j': ('KeyJ', 74),
    'k': ('KeyK', 75), 'l': ('KeyL', 76), 'm': ('KeyM', 77), 'n': ('KeyN', 78), 'o': ('KeyO', 79),
    'p': ('KeyP', 80), 'q': ('KeyQ', 81), 'r': ('KeyR', 82), 's': ('KeyS', 83), 't': ('KeyT', 84),
    'u': ('KeyU', 85), 'v': ('KeyV', 86), 'w': ('KeyW', 87), 'x': ('KeyX', 88), 'y': ('KeyY', 89),
    'z': ('KeyZ', 90), 'A': ('KeyA', 65), 'B': ('KeyB', 66), 'C': ('KeyC', 67), 'D': ('KeyD', 68),
    'E': ('KeyE', 69), 'F': ('KeyF', 70), 'G': ('KeyG', 71), 'H': ('KeyH', 72), 'I': ('KeyI', 73),
    'J': ('KeyJ', 74), 'K': ('KeyK', 75), 'L': ('KeyL', 76), 'M': ('KeyM', 77), 'N': ('KeyN', 78),
    'O': ('KeyO', 79), 'P': ('KeyP', 80), 'Q': ('KeyQ', 81), 'R': ('KeyR', 82), 'S': ('KeyS', 83),
    'T': ('KeyT', 84), 'U': ('KeyU', 85), 'V': ('KeyV', 86), 'W': ('KeyW', 87), 'X': ('KeyX', 88),
    'Y': ('KeyY', 89), 'Z': ('KeyZ', 90), '0': ('Digit0', 48), '1': ('Digit1', 49), '2': ('Digit2', 50),
    '3': ('Digit3', 51), '4': ('Digit4', 52), '5': ('Digit5', 53), '6': ('Digit6', 54), '7': ('Digit7', 55),
    '8': ('Digit8', 56), '9': ('Digit9', 57), '!': ('Digit1', 49), '"': ('Quote', 222), '#': ('Digit3', 51),
    '$': ('Digit4', 52), '%': ('Digit5', 53), '&': ('Digit7', 55), "'": ('Quote', 222), '(': ('Digit9', 57),
    ')': ('Digit0', 48), '*': ('Digit8', 56), '+': ('Equal', 187), ',': ('Comma', 188), '-': ('Minus', 189),
    '.': ('Period', 190), '/': ('Slash', 191), ':': ('Semicolon', 186), ';': ('Semicolon', 186),
    '<': ('Comma', 188),
    '=': ('Equal', 187), '>': ('Period', 190), '?': ('Slash', 191), '@': ('Digit2', 50),
    '[': ('BracketLeft', 219),
    '\\': ('Backslash', 220), ']': ('BracketRight', 221), '^': ('Digit6', 54), '_': ('Minus', 189),
    '`': ('Backquote', 192),
    '{': ('BracketLeft', 219), '|': ('Backslash', 220), '}': ('BracketRight', 221), '~': ('Backquote', 192),
    ' ': ('Space', 32), '\r': ('Enter', 13)
}

SHIFT_KEY_NEEDED = '~!@#$%^&*()_+{}|:"<>?'


class NoSuchIframe(Exception):
    reference: typing.Union[WebElement, int, str]

    def __init__(self, reference: typing.Union[WebElement, int, str], message: str):
        self.reference = reference
        super().__init__(message)


class Target:
    """the Target class

    Usually a tab, (cors-)iframe, WebWorker etc.
    """

    # noinspection PyShadowingBuiltins
    def __init__(self, host: str, target_id: str, driver, context, is_remote: bool = False,
                 loop: asyncio.AbstractEventLoop or None = None, timeout: float = 30,
                 type: str = None, start_socket: bool = False, max_ws_size: int = 2 ** 20) -> None:
        from selenium_driverless.types.context import Context
        self._parent_target = None
        self._context: Context = context
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
        self._send_key_lock = asyncio.Lock()

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
        return self._driver.base_target

    @property
    def socket(self) -> SingleCDPSocket:
        """the cdp-socket for the connection"""
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
        """
        find targets for a list of iframes

        :param iframes: iframes to find targets for

        .. warning::

            only CORS iframes have its own target,
            you might use :func:`WebElement.content_document <selenium_driverless.types.webelement.WebElement.content_document>`
            instead

        """
        if not iframes:
            raise ValueError(f"Expected WebElements, but got{iframes}")

        async def target_getter(target_id: str, timeout: float = 2, max_ws_size: int = 2 ** 20):
            return await get_target(target_id=target_id, host=self._host, loop=self._loop, is_remote=self._is_remote,
                                    timeout=timeout, max_ws_size=max_ws_size, driver=self._driver,
                                    context=self._context)

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
        """
        find a target for an iframe

        :param iframe: iframe to find target for

        .. warning::

            only CORS iframes have its own target,
            you might use :func:`WebElement.content_document <selenium_driverless.types.webelement.WebElement.content_document>`
            instead

        """
        targets = await self.get_targets_for_iframes([iframe])
        if not targets:
            raise NoSuchIframe(iframe, "no target for iframe found")
        return targets[0]

    async def wait_download(self, timeout: float or None = 30) -> dict:
        """
        wait for a download on the current tab

        returns something like

        .. code-block:: python

            {
                "frameId": "2D543B5E8B14945B280C537A4882A695",
                "guid": "c91df4d5-9b45-4962-84df-3749bd3f926d",
                "url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
                "suggestedFilename": "dummy.pdf",

                # only if options.downloads_dir specified
                "guid_file": "D:\\System\\AppData\\PyCharm\\scratches\\downloads\\c91df4d5-9b45-4962-84df-3749bd3f926d"
            }

        :param timeout: time in seconds to wait for a download

        .. warning::
            downloads from iframes not supported yet

        """

        # todo: support downloads from iframes
        async def _wait_download():
            base_frame = await self.base_frame
            _id = base_frame.get("id")
            _dir = [self._context.downloads_dir][0]
            async for data in await self.base_target.get_cdp_event_iter("Browser.downloadWillBegin"):
                base_frame = await self.base_frame
                curr_id = base_frame.get("id")
                if data["frameId"] in [_id, curr_id]:
                    if _dir:
                        guid_file = str(pathlib.Path(_dir + "/" + data["guid"]))
                        named_file = str(pathlib.Path(_dir + "/" + "suggestedFilename"))
                        data["guid_file"] = guid_file
                        data["named_file"] = named_file
                        while not (os.path.exists(guid_file) or os.path.exists(named_file)):
                            # wait for file to exist
                            await asyncio.sleep(0.01)
                    return data

        return await asyncio.wait_for(_wait_download(), timeout=timeout)

    # noinspection PyUnboundLocalVariable,PyProtectedMember
    async def get(self, url: str, referrer: str = None, wait_load: bool = True, timeout: float = 30) -> dict:
        """Loads a web page

        :param url: the url to load.
        :param referrer: the referrer to load the page with
        :param wait_load: whether to wait for the webpage to load
        :param timeout: the maximum time in seconds for waiting on load

        returns the same as :func:`Target.wait_download <selenium_driverless.types.target.Target.wait_download>` if the url initiates a download
        """
        if url == "about:blank":
            wait_load = False
        result = {}

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

            # wait for download or loadEventFired
            wait = asyncio.ensure_future(asyncio.wait([
                safe_wrap_fut(self.wait_for_cdp("Page.loadEventFired", timeout=None)),
                safe_wrap_fut(self.wait_download(timeout=None))
            ], timeout=timeout, return_when=asyncio.FIRST_COMPLETED))

            await asyncio.sleep(0.01)  # ensure listening for events has already started

        # send navigate cmd
        args = {"url": url, "transitionType": "link"}
        if referrer:
            args["referrer"] = referrer
        get = asyncio.ensure_future(self.execute_cdp_cmd("Page.navigate", args, timeout=timeout))

        if wait_load:
            done, pending = await wait
            pending.pop().cancel()
            if not done:
                pending.pop().cancel()
                try:
                    await get  # ensure get is awaited in every case
                except Exception as e:
                    raise e
                raise asyncio.TimeoutError(f'page: "{url}" didn\'t load within timeout of {timeout}')
            result = done.pop().result()  # data of the event waited for
        try:
            await get  # wait for navigate cmd response
        except Exception as e:
            raise e
        await self._on_loaded()
        return result

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
            try:
                res = await self.execute_cdp_cmd("Runtime.evaluate", args)
            except CDPError as e:
                if e.code == -32000 and e.message == 'Cannot find context with specified id':
                    raise StaleJSRemoteObjReference("GlobalThis")
                else:
                    raise e

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
        """the :class:`Pointer <selenium_driverless.input.pointer.Pointer>` for this target"""
        return self._pointer

    async def send_keys(self, text: str, allow_not_on_mapping: bool = True):
        """
        send text & keys to the target

        :param text: the text to send to the target
        :param allow_not_on_mapping: allow keys which aren't int the keyboard mapping
        """
        async with self._send_key_lock:
            for letter in text:
                if letter in KEY_MAPPING:
                    if letter == "\n":
                        letter = "\r"
                    key_code, virtual_key_code = KEY_MAPPING[letter]
                elif allow_not_on_mapping:
                    key_code, virtual_key_code = 0, 0
                else:
                    raise ValueError(f"letter:{letter} not in keyboard mapping")

                # Determine if a shift key is needed
                shift_pressed = False
                if letter.isupper() or letter in SHIFT_KEY_NEEDED:
                    shift_pressed = True
                    await self.execute_cdp_cmd("Input.dispatchKeyEvent", {
                        "type": "keyDown",
                        "code": "ShiftLeft",
                        "windowsVirtualKeyCode": 16,
                        "key": "Shift",
                        "modifiers": 8 if shift_pressed else 0
                    })
                await asyncio.sleep(random.uniform(0.01, 0.05))  # Simulate human typing speed

                key_event = {
                    "type": "keyDown",
                    "code": key_code,
                    "windowsVirtualKeyCode": virtual_key_code,
                    "key": letter,
                    "modifiers": 8 if shift_pressed else 0
                }

                # Send keydown event
                await self.execute_cdp_cmd("Input.dispatchKeyEvent", key_event)
                await asyncio.sleep(random.uniform(0.01, 0.05))

                # Simulate key press for the actual character
                key_event["type"] = "char"
                key_event["text"] = letter
                await self.execute_cdp_cmd("Input.dispatchKeyEvent", key_event)
                await asyncio.sleep(random.uniform(0.01, 0.05))
                del key_event['text']

                # Simulate key release
                key_event["type"] = "keyUp"
                await self.execute_cdp_cmd("Input.dispatchKeyEvent", key_event)
                await asyncio.sleep(random.uniform(0.01, 0.05))

                # Release the shift key if it was pressed
                if shift_pressed:
                    await self.execute_cdp_cmd("Input.dispatchKeyEvent", {
                        "type": "keyUp",
                        "code": "ShiftLeft",
                        "windowsVirtualKeyCode": 16,
                        "key": "Shift",
                        "modifiers": 0
                    })
                    await asyncio.sleep(random.uniform(0.01, 0.05))  # Simulate human typing speed

    async def execute_raw_script(self, script: str, *args, await_res: bool = False, serialization: str = None,
                                 max_depth: int = None, timeout: float = 2, execution_context_id: str = None,
                                 unique_context: bool = True):
        """executes a JavaScript on ``GlobalThis`` such as

        .. code-block:: js

            function(...arguments){return document}

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

        start = time.perf_counter()
        exc = None
        while (time.perf_counter() - start) > timeout:
            try:
                global_this = await self._global_this(execution_context_id)
                res = await global_this.__exec_raw__(script, *args, await_res=await_res, serialization=serialization,
                                                     max_depth=max_depth, timeout=timeout,
                                                     execution_context_id=execution_context_id, unique_context=False)
            except StaleJSRemoteObjReference as e:
                exc = e
            else:
                return res
        if exc:
            raise exc
        else:
            raise asyncio.TimeoutError(f"Couldn't execute script due to stale reference within {timeout} s, "
                                       f"possibly due to a reload loop")

    async def execute_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                             timeout: float = 2, execution_context_id: str = None,
                             unique_context: bool = True):
        """executes JavaScript synchronously on ``GlobalThis`` such as

        .. code-block:: js

            return document

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        if execution_context_id and unique_context:
            warnings.warn("got execution_context_id and unique_context=True, defaulting to execution_context_id")
        if unique_context:
            execution_context_id = await self._isolated_context_id
        if timeout is None:
            timeout = 2

        start = time.perf_counter()
        while (time.perf_counter() - start) < timeout:
            global_this = await self._global_this(execution_context_id)
            try:
                res = await global_this.__exec__(script, *args, serialization=serialization,
                                                 max_depth=max_depth, timeout=timeout,
                                                 execution_context_id=execution_context_id,
                                                 unique_context=False)
                return res
            except StaleJSRemoteObjReference:
                pass
        raise asyncio.TimeoutError("Couldn't execute script, possibly due to a reload loop")

    async def execute_async_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                                   timeout: float = 2, execution_context_id: str = None,
                                   unique_context: bool = None):
        """executes JavaScript asynchronously on ``GlobalThis``

        .. code-block:: js

            resolve = arguments[arguments.length-1]

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        if execution_context_id and unique_context:
            warnings.warn("got execution_context_id and unique_context=True, defaulting to execution_context_id")
        if unique_context:
            execution_context_id = await self._isolated_context_id
        if timeout is None:
            timeout = 2

        start = time.perf_counter()
        while (time.perf_counter() - start) < timeout:
            global_this = await self._global_this(execution_context_id)
            try:
                res = await global_this.__exec_async__(script, *args, serialization=serialization,
                                                       max_depth=max_depth, timeout=timeout,
                                                       execution_context_id=execution_context_id,
                                                       unique_context=False)
                return res
            except StaleJSRemoteObjReference:
                await asyncio.sleep(0)
        raise asyncio.TimeoutError("Couldn't execute script, possibly due to a reload loop")

    async def eval_async(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                         timeout: float = 2, execution_context_id: str = None,
                         unique_context: bool = True):
        """executes JavaScript asynchronously on ``GlobalThis`` such as

        .. code-block:: js

            res = await fetch("https://httpbin.org/get");
            // mind CORS!
            json = await res.json()
            return json

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        if execution_context_id and unique_context:
            warnings.warn("got execution_context_id and unique_context=True, defaulting to execution_context_id")
        if unique_context:
            execution_context_id = await self._isolated_context_id
        if timeout is None:
            timeout = 2

        start = time.perf_counter()
        while (time.perf_counter() - start) < timeout:
            global_this = await self._global_this(execution_context_id)
            try:
                res = await global_this.__eval_async__(script, *args, serialization=serialization,
                                                       max_depth=max_depth, timeout=timeout,
                                                       execution_context_id=execution_context_id,
                                                       unique_context=False)
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
        """Gets the HTML of the current page.
        """
        start = time.perf_counter()
        timeout = 10
        while (time.perf_counter() - start) < timeout:
            try:
                elem = await self._document_elem
                return await elem.source
            except StaleElementReferenceException:
                await self._on_loaded()
        raise asyncio.TimeoutError(
            f"Couldn't get page source within {timeout} seconds, possibly due to a reload loop")

    async def close(self, timeout: float = 2) -> None:
        """Closes the current window.

        :Usage:
            ::

                target.close()
        """
        try:
            await self.execute_cdp_cmd("Target.closeTarget", {"targetId": self.id}, timeout=timeout)
            await self._socket.close()
        except websockets.ConnectionClosedError:
            pass
        except (asyncio.TimeoutError, TimeoutError):
            pass

    async def focus(self, activate=False):
        """
        emulates Focus of the target

        :param activate: whether to bring the window to the front
        """
        if activate:
            await self.activate()
        try:
            await self.execute_cdp_cmd("Emulation.setFocusEmulationEnabled", {"enabled": True})
        except CDPError as e:
            if not (e.code == -32601 and e.message == "'Emulation.setFocusEmulationEnabled' wasn't found"):
                raise e

    async def unfocus(self):
        """
        disables focus emulation for the target
        """
        try:
            await self.execute_cdp_cmd("Emulation.setFocusEmulationEnabled", {"enabled": False})
        except CDPError as e:
            if e.code == -32601 and e.message == "'Target.activateTarget' wasn't found":
                return False
            raise e

    async def activate(self):
        """
        brings the window to the front
        """
        try:
            await self.execute_cdp_cmd("Target.activateTarget", {"targetId": self.id})
        except CDPError as e:
            if e.code == -32601 and e.message == "'Target.activateTarget' wasn't found":
                return False
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

    async def print_page(self) -> str:
        """Takes PDF of the current page.

        The target makes the best effort to return a PDF based on the
        provided parameters.

        returns Base64-encoded pdf data as a string
        """
        page = await self.execute_cdp_cmd("Page.printToPDF")
        return page["data"]

    async def get_history(self) -> TypedDict('NavigationHistory', {'currentIndex': int, 'entries': list}):
        """returns the history data

        see `Page.getNavigationHistory <https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-getNavigationHistory>`__
        """
        return await self.execute_cdp_cmd("Page.getNavigationHistory")

    # Navigation
    async def back(self) -> None:
        """Goes one step backward in the browser history.
        """
        history = await self.get_history()
        entry = history["entries"][history['currentIndex'] - 1]["id"]
        await self.execute_cdp_cmd("Page.navigateToHistoryEntry", {"entryId": entry})
        await self._on_loaded()

    async def forward(self) -> None:
        """Goes one step forward in the browser history.
        """
        history = await self.get_history()
        entry = history["entries"][history["currentIndex"] + 1]["id"]
        await self.execute_cdp_cmd("Page.navigateToHistoryEntry", {"entryId": entry})
        await self._on_loaded()

    async def refresh(self) -> None:
        """Refreshes the page.
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
        context_id = None
        # noinspection PyProtectedMember
        if self._context._is_incognito:
            context_id = self.browser_context_id
        return await add_cookie(target=self, cookie_dict=cookie_dict, context_id=context_id)

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
    async def find_element(self, by: str, value: str, timeout: float or None = None) -> WebElement:
        """find an element in the current target

        :param by: one of the locators at :func:`By <selenium_driverless.types.by.By>`
        :param value: the actual query to find the element by
        :param timeout: how long to wait for the element to exist
        """
        start = time.perf_counter()
        elem = None
        while not elem:
            parent = await self._document_elem
            try:
                elem = await parent.find_element(by=by, value=value, timeout=None)
            except (StaleElementReferenceException, NoSuchElementException, StaleJSRemoteObjReference):
                await self._on_loaded()
            if (not timeout) or (time.perf_counter() - start) > timeout:
                break
            await asyncio.sleep(0.01)
        if not elem:
            raise NoSuchElementException()
        return elem

    async def find_elements(self, by: str, value: str, timeout: float = 3) -> typing.List[WebElement]:
        """find multiple elements in the current target

        :param by: one of the locators at :func:`By <selenium_driverless.types.by.By>`
        :param value: the actual query to find the elements by
        :param timeout: how long to wait for not being in a page reload loop in seconds
        """
        start = time.perf_counter()
        while True:
            parent = await self._document_elem
            try:
                return await parent.find_elements(by=by, value=value)
            except (StaleElementReferenceException, StaleJSRemoteObjReference):
                await self._on_loaded()
            if (not timeout) or (time.perf_counter() - start) > timeout:
                raise asyncio.TimeoutError(
                    f"Couldn't find elements within {timeout} seconds due to a target reload loop")

    async def set_source(self, source: str, timeout: float = 15):
        """
        sets the OuterHtml of the current target (if it has DOM//HTML)

        :param source: the html
        :param timeout: the timeout to try setting the source (might fail if the page is in a reload-loop
        """
        start = time.perf_counter()
        while (time.perf_counter() - start) < timeout:
            try:
                document = await self._document_elem
                await document.set_source(source)
                return
            except StaleElementReferenceException:
                await self._on_loaded()
                await asyncio.sleep(0)
        raise asyncio.TimeoutError("Couldn't get document element to not be stale")

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

    async def get_screenshot_as_file(self, filename: str) -> None:
        """Saves a screenshot of the current window to a PNG image file.

        :param filename: The full path.
            This should end with a `.png` extension.
        """
        if not str(filename).lower().endswith(".png"):
            warnings.warn(
                "name used for saved screenshot does not match file " "type. It should end with a `.png` extension",
                UserWarning,
            )
        png = await self.get_screenshot_as_png()
        async with aiofiles.open(filename, "wb") as f:
            await f.write(png)

    async def save_screenshot(self, filename: str) -> None:
        """alias to :func: `driver.get_screenshot_as_file <selenium_driverless.webdriver.Chrome.get_screenshot_as_file>`"""
        return await self.get_screenshot_as_file(filename)

    async def get_screenshot_as_png(self) -> bytes:
        """Gets the screenshot of the current window as a binary data.
        """
        res = await self.execute_cdp_cmd("Page.captureScreenshot", {"format": "png"}, timeout=30)
        return b64decode(res["data"].encode("ascii"))

    async def snapshot(self) -> str:
        """gets the current snapshot as mhtml"""
        res = await self.execute_cdp_cmd("Page.captureSnapshot")
        return res["data"]

    async def save_snapshot(self, filename: str):
        """Saves a snapshot of the current window to a MHTML file.

        :param filename: The full path you wish to save your snapshot to. This
                   should end with a ``.mhtml`` extension.

        .. code-block:: Python

            await driver.get_snapshot('snapshot.mhtml')

        """

        if len(filename) <= 6 or filename[-6:] != ".mhtml":
            warnings.warn(
                "name used for saved snapshot does not match file " "type. It should end with a `.mhtml` extension",
                UserWarning,
            )
        mhtml = await self.snapshot()
        async with aiofiles.open(filename, "w") as f:
            await f.write(mhtml)

    async def get_network_conditions(self):
        """Gets Chromium network emulation settings.

        :Returns:
            A dict. For example:
            {'latency': 4, 'download_throughput': 2, 'upload_throughput': 2,
            'offline': False}
        """
        raise NotImplementedError("not started with chromedriver")

    async def set_network_conditions(self, offline: bool, latency: int, download_throughput: int,
                                     upload_throughput: int,
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

    async def wait_for_cdp(self, event: str, timeout: float or None = None) -> dict:
        """
        wait for a CDP event and return the data
        :param event: the name of the event
        :param timeout: timeout to wait in seconds.
        """
        if not self.socket:
            await self._init()
        return await self.socket.wait_for(event, timeout=timeout)

    async def add_cdp_listener(self, event: str, callback: typing.Callable[[dict], any]):
        """add a listener on a CDP event (current target)

        :param event: the name of the event
        :param callback: the callback on the event

        .. note::
            callback has to accept one parameter (event data as json)

        """
        if not self.socket:
            await self._init()
        self.socket.add_listener(method=event, callback=callback)

    async def remove_cdp_listener(self, event: str, callback: typing.Callable[[dict], any]):
        """
        removes the CDP listener
        :param event: the name of the event
        :param callback: the callback to remove
        """
        if not self.socket:
            await self._init()
        self.socket.remove_listener(method=event, callback=callback)

    async def get_cdp_event_iter(self, event: str) -> typing.AsyncIterable[dict]:
        """
        iterate over a cdp event

        :param event: name of the event to iterate over

        .. code-block:: Python

            async for data in await target.get_cdp_event_iter("Page.frameNavigated"):
                print(data["frame"]["url"]


        .. warning::
            **async only** supported for now

        """
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

    async def fetch(self, url: str,
                    method: typing.Literal[
                        "GET", "POST", "HEAD", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", None] = "GET",
                    headers: typing.Dict[str, str] = None, body: typing.Union[bytes, str, dict] = None,
                    mode: typing.Literal["cors", "no-cors", "same-origin", None] = None,
                    credentials: typing.Literal["omit", "same-origin", "include"] = None,
                    cache: typing.Literal[
                        "default", "no-store", "reload", "no-cache", "force-cache", "only-if-cached"] = None,
                    redirect: typing.Literal["follow", "error"] = None, referrer: str = None,
                    referrer_policy: typing.Literal[
                        "no-referrer", "no-referrer-when-downgrade", "same-origin", "origin", "strict-origin", "origin-when-cross-origin", "strict-origin-when-cross-origin", "unsafe-url"] = None,
                    integrity: str = None, keepalive=None,
                    priority: typing.Literal["high", "low", "auto", None] = "high", timeout: float = 20) -> dict:
        """
        executes a JS ``fetch`` request within the target,
        see `developer.mozilla.org/en-US/docs/Web/API/fetch <https://developer.mozilla.org/en-US/docs/Web/API/fetch>`_ for reference

        returns smth like

        .. code-block:: Python

            {
                "body":bytes,
                "headers":dict,
                "ok":bool,
                "status_code":int,
                "redirected":bool,
                "status_text":str,
                "type":str,
                "url":str
            }

        """
        loop = asyncio.get_event_loop()
        if isinstance(body, dict):
            body = await loop.run_in_executor(None, lambda: json.dumps(body).encode("utf-8"))
        elif isinstance(body, str):
            body = await loop.run_in_executor(None, lambda: body.encode("utf-8"))
        options = {}
        if method:
            options["method"] = method
        if headers:
            options["headers"] = headers
        if body:
            options["body"] = await loop.run_in_executor(None, lambda: base64.b64encode(body).decode("ascii"))
        if mode:
            options["mode"] = mode
        if credentials:
            options["credentials"] = credentials
        if cache:
            options["cache"] = cache
        if redirect:
            options["redirect"] = redirect
        if referrer:
            options["referrer"] = referrer
        if referrer_policy:
            options["referrerPolicy"] = referrer_policy
        if integrity:
            options["integrity"] = integrity
        if keepalive:
            options["keepalive"] = keepalive
        if priority:
            options["priority"] = priority

        script = """
            async function bufferTobase64(array) {
              return new Promise((resolve) => {
                const blob = new Blob([array]);
                const reader = new FileReader();
                
                reader.onload = (event) => {
                  const dataUrl = event.target.result;
                  const [_, base64] = dataUrl.split(',');
                  
                  resolve(base64);
                };
                
                reader.readAsDataURL(blob);
              });
            };
            async function base64ToBuffer(base64) {
              const dataUrl = "data:application/octet-binary;base64," + base64;
            
              const res = await fetch(dataUrl)
              return await res.arrayBuffer()
            };

            function headers2dict(headers){
                var my_dict = {};
                for (var pair of headers.entries()) {
                        my_dict[pair[0]] = pair[1]};
                return my_dict}

            async function get(url, options){
                if(options.body){options.body = await base64ToBuffer(options.body)}
                var response = await fetch(url, options);
                var buffer = await response.arrayBuffer()
                var b64 = await bufferTobase64(buffer)
                var res = {
                        "b64":b64,
                        "headers":headers2dict(response.headers),
                        "ok":response.ok,
                        "status_code":response.status,
                        "redirected":response.redirected,
                        "status_text":response.statusText,
                        "type":response.type,
                        "url":response.url
                        };
                return res;
            }
            return await get(arguments[0], arguments[1])
        """
        result = await self.eval_async(script, url, options, unique_context=True, timeout=timeout)
        result["body"] = base64.b64decode(result["b64"])
        del result["b64"]
        return result

    async def xhr(self, url: str,
                  method: typing.Literal["GET", "POST", "PUT", "DELETE"] = "GET",
                  body: typing.Union[bytes, str, dict] = None,
                  user: str = None, password: str = None, with_credentials: bool = True, mime_type: str = "text/plain",
                  extra_headers: typing.Dict[str, str] = None,
                  timeout: float = 30) -> dict:
        """
        executes a JS ``XMLHttpRequest`` request within the target,
        see `developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest <https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest>`_ for reference

        :param url: the url to get
        :param method: one of "GET", "POST", "PUT", "DELETE"
        :param body: body to send with a request
        :param user: user to authenticate with
        :param password: password to authenticate with
        :param with_credentials: whether to include cookies
        :param mime_type: the type to parse the response as
        :param extra_headers: a key/value dict of extra headers to add to the request
        :param timeout: timeout in seconds for the request to take

        returns smth like

        .. code-block:: Python

            {
                "status": int,
                "response": any,
                "responseText":str,
                "responseType":str,
                "responseURL":str,
                "responseXML":any,
                "statusText":str,
                "responseHeaders":dict
            }

        """
        if extra_headers is None:
            extra_headers = {}
        loop = asyncio.get_event_loop()
        if isinstance(body, dict):
            body = await loop.run_in_executor(None, lambda: json.dumps(body).encode("utf-8"))
        elif isinstance(body, str):
            body = await loop.run_in_executor(None, lambda: body.encode("utf-8"))
        if body is not None:
            body = await loop.run_in_executor(None, lambda: base64.b64encode(body).decode("ascii"))
        script = """
        async function base64ToBuffer(base64) {
              const dataUrl = "data:application/octet-binary;base64," + base64;
            
              const res = await fetch(dataUrl)
              return await res.arrayBuffer()
        };
        async function makeRequest(withCredentials, mimeType, extraHeaders, method, url, user, password, body) {
            let xhr = new XMLHttpRequest();

            if(!user){user = null};
            if(!password){password = null};
            if(!body){body = null}else{body = await base64ToBuffer(body)};
            xhr.overrideMimeType(mimeType);

            xhr.open(method, url, true, user, password);
            Object.keys(extraHeaders).forEach((key) => {
                xhr.setRequestHeader(key, extraHeaders[key])
            });
            xhr.withCredentials = withCredentials;
            const promise = new Promise((resolve, reject) => {
                xhr.onload = () => {resolve(xhr)};
                xhr.onerror = () => {reject(new Error("XHR failed"))};
            });
            xhr.send(body);
            return await promise
        };
        var xhr =  await makeRequest(...arguments);
        data = {
            status: xhr.status,
            response: xhr.response,
            responseText:xhr.responseText,
            responseType:xhr.responseType,
            responseURL:xhr.responseURL,
            responseXML:xhr.responseXML,
            statusText:xhr.statusText,
            responseHeaders:xhr.getAllResponseHeaders()

        };
        return data
        """
        data = await self.eval_async(script, with_credentials, mime_type,
                                     extra_headers, method, url, user, password, body,
                                     timeout=timeout, unique_context=True)

        # parse headers
        headers = data['responseHeaders']
        if headers == "null":
            _headers = {}
        else:
            headers = headers.split("\r\n")
            _headers = {}
            for header in headers:
                header = header.split(': ')
                if len(header) == 2:
                    key, value = header
                    _headers[key] = value
        data['responseHeaders'] = _headers

        # todo: parse different response types
        return data

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

        :param sink_name: Name of the sink to use as the target.
        """
        return await self.execute_cdp_cmd("Cast.startTabMirroring", {"sinkName": sink_name})

    async def stop_casting(self, sink_name: str) -> dict:
        """Stops the existing Cast session on a specific receiver target.

        :param sink_name: Name of the sink to stop the Cast session.
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
