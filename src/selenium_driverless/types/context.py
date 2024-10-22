# Licensed to the Software Freedom Conservancy (SFC) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The SFC licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# modified by kaliiiiiiiiii | Aurin Aegerter
# all modifications are licensed under the license provided at LICENSE.md

"""The WebDriver implementation."""
import inspect
import time
import os
import typing
import warnings
import pathlib

from typing import List

# io
import asyncio
import websockets
from cdp_socket.exceptions import CDPError

# selenium
# SwitchTo
from selenium_driverless.scripts.switch_to import SwitchTo
from selenium_driverless.sync.switch_to import SwitchTo as SyncSwitchTo

# targets
from selenium_driverless.types.base_target import BaseTarget
from selenium_driverless.types.target import Target, TargetInfo
from selenium_driverless.scripts.driver_utils import get_targets, get_target

# other
from selenium_driverless.input.pointer import Pointer
from selenium_driverless.types.webelement import WebElement
from selenium_driverless.utils.utils import check_timeout


class Context:
    """Allows you to drive the browser without chromedriver."""
    _is_incognito: bool

    # noinspection PyProtectedMember
    def __init__(self, base_target: Target, driver, context_id: str = None,
                 loop: asyncio.AbstractEventLoop = None,
                 is_incognito: bool = False, max_ws_size: int = 2 ** 20) -> None:
        self._loop: asyncio.AbstractEventLoop or None = None
        self.browser_pid: int or None = None
        self._targets: typing.Dict[str, Target] = {}

        self._switch_to = None
        self._started = False
        self._loop = loop

        self._current_target = base_target
        self._host = base_target._host
        self._is_remote = base_target._is_remote
        self._max_ws_size: int = max_ws_size

        self._context_id = context_id
        self._closed_callbacks: typing.List[callable] = []
        self._driver = driver
        self._is_incognito = is_incognito

    def __repr__(self):
        return f'<{type(self).__module__}.{type(self).__name__} (session="{self.current_window_handle}")>'

    async def __aenter__(self):
        await self.start_session()
        return self

    def __enter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.quit()

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __await__(self):
        return self.start_session().__await__()

    async def start_session(self):
        from selenium_driverless.webdriver import Chrome
        self._driver: Chrome

        if not self._started:
            if not self.context_id:
                self._context_id = await self._current_target.browser_context_id
            _type = await self.current_target.type
            targets = None
            if not _type == "page:":
                targets = await self.targets
                for _id, info in list(targets.items()):
                    if info.type == "page" and not info.url.startswith("chrome-extension://"):
                        self._current_target = info.Target
                        break
                    else:
                        del targets[_id]
            if self._loop:
                self._switch_to = await SyncSwitchTo(context=self, loop=self._loop, context_id=self._context_id)
            else:
                self._switch_to = await SwitchTo(context=self, loop=self._loop, context_id=self._context_id)
            if targets:
                await self.current_target.focus(activate=False)
            self._started = True
        return self

    @property
    async def frame_tree(self):
        return await self.current_target.frame_tree

    @property
    async def targets(self) -> typing.Dict[str, TargetInfo]:
        return await self.get_targets()

    async def get_targets(self, _type: str = None, context_id="self") -> typing.Dict[str, TargetInfo]:
        if context_id == "self":
            context_id = self.context_id
        return await get_targets(cdp_exec=self.base_target.execute_cdp_cmd, target_getter=self.get_target, _type=_type,
                                 context_id=context_id, max_ws_size=self._max_ws_size)

    @property
    def current_target(self) -> Target:
        return self._current_target

    @property
    def base_target(self) -> BaseTarget:
        return self._driver.base_target

    @property
    async def _isolated_context_id(self):
        # noinspection PyProtectedMember
        return await self.current_target._isolated_context_id

    async def get_target(self, target_id: str = None, timeout: float = 2, max_ws_size: int = None) -> Target:
        if not max_ws_size:
            max_ws_size = self._max_ws_size
        if not target_id:
            return self._current_target
        target: Target = self._targets.get(target_id)
        if not target:
            target: Target = await get_target(target_id=target_id, host=self._host,
                                              loop=self._loop, is_remote=self._is_remote, timeout=timeout,
                                              max_ws_size=max_ws_size, driver=self._driver, context=self)
            self._targets[target_id] = target

            # noinspection PyUnusedLocal
            def remove_target(code: str, reason: str):
                if target_id in self._targets:
                    del self._targets[target_id]

            # noinspection PyProtectedMember
            target._on_closed.append(remove_target)
        return target

    async def get_target_for_iframe(self, iframe: WebElement):
        return await self.current_target.get_target_for_iframe(iframe=iframe)

    async def set_download_behaviour(self, behavior: typing.Literal["deny", "allow", "allowAndName", "default"],
                                     path: str = None):
        """set the download behaviour

        :param behavior: the behaviour to set the downloading to
        :param path: the path to the default download directory

        .. warning::
            setting ``behaviour=allow`` instead of ``allowAndName`` can cause some bugs

        """
        params = {"behavior": behavior, "eventsEnabled": True}
        if path:
            _dir = str(pathlib.Path(path))
            if os.path.isfile(_dir):
                raise OSError("path can't point to a file")
            params["downloadPath"] = _dir
        if self._is_incognito:
            params["browserContextId"] = self.context_id
        await self.base_target.execute_cdp_cmd("Browser.setDownloadBehavior", params)

    @property
    def downloads_dir(self):
        """the current downloads directory"""
        if self._is_incognito:
            return self.base_target.downloads_dir_for_context(context_id=self.context_id)
        else:
            return self.base_target.downloads_dir_for_context(context_id="DEFAULT")

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
        return await self.current_target.wait_download(timeout=timeout)

    async def get(self, url: str, referrer: str = None, wait_load: bool = True, timeout: float = 30) -> dict:
        """Loads a web page in the current Target

        :param url: the url to load.
        :param referrer: the referrer to load the page with
        :param wait_load: whether to wait for the webpage to load
        :param timeout: the maximum time in seconds for waiting on load

        returns the same as :func:`Target.wait_download <selenium_driverless.types.target.Target.wait_download>` if the url initiates a download
        """
        if self._is_incognito and url in ["chrome://extensions"]:
            raise ValueError(f"{url} only supported in non-incognito contexts")
        target = self.current_target
        return await target.get(url=url, referrer=referrer, wait_load=wait_load, timeout=timeout)

    @property
    async def title(self) -> str:
        """Returns the title of the current target"""
        target = await self.current_target_info
        return target.title

    @property
    def current_pointer(self) -> Pointer:
        """the :class:`Pointer <selenium_driverless.input.pointer.Pointer>` for the current target"""
        target = self.current_target
        return target.pointer

    async def send_keys(self, text: str):
        """
        send text & keys to the current target

        :param text: the text to send
        """
        await self.current_target.send_keys(text)

    async def execute_raw_script(self, script: str, *args, await_res: bool = False, serialization: str = None,
                                 max_depth: int = None, timeout: float = 2,
                                 execution_context_id: str = None, unique_context: bool = True):
        """
        example:
        script= "function(...arguments){obj.click()}"
        "const obj" will be the Object according to obj_id
        """
        return await self.current_target.execute_raw_script(script, *args, await_res=await_res,
                                               serialization=serialization, max_depth=max_depth,
                                               timeout=timeout, execution_context_id=execution_context_id,
                                               unique_context=unique_context)

    async def execute_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                             timeout: float = 2, execution_context_id: str = None,
                             unique_context: bool = True):
        """executes JavaScript synchronously on ``GlobalThis`` such as

        .. code-block:: js

            return document

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        return await self.current_target.execute_script(script, *args, max_depth=max_depth, serialization=serialization,
                                                        timeout=timeout, execution_context_id=execution_context_id,
                                                        unique_context=unique_context)

    async def execute_async_script(self, script: str, *args, max_depth: int = 2,
                                   serialization: str = None, timeout: float = 2,
                                   execution_context_id: str = None,
                                   unique_context: bool = True):
        """executes JavaScript asynchronously on ``GlobalThis`` such as

        .. warning::
            using execute_async_script is not recommended as it doesn't handle exceptions correctly.
            Use :func:`Chrome.eval_async <selenium_driverless.webdriver.Chrome.eval_async>`

        .. code-block:: js

            resolve = arguments[arguments.length-1]

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        return await self.current_target.execute_async_script(script, *args, max_depth=max_depth,
                                                              serialization=serialization,
                                                              timeout=timeout,
                                                              execution_context_id=execution_context_id,
                                                              unique_context=unique_context)

    async def eval_async(self, script: str, *args, max_depth: int = 2,
                         serialization: str = None, timeout: float = 2,
                         execution_context_id: str = None,
                         unique_context: bool = True):
        """executes JavaScript asynchronously on ``GlobalThis`` such as

        .. code-block:: js

            res = await fetch("https://httpbin.org/get");
            // mind CORS!
            json = await res.json()
            return json

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        return await self.current_target.eval_async(script, *args, max_depth=max_depth, serialization=serialization,
                                                    timeout=timeout,
                                                    execution_context_id=execution_context_id,
                                                    unique_context=unique_context)

    @property
    async def current_url(self) -> str:
        """Gets the URL of the current page.

        :Usage:
            ::

                target.current_url
        """
        target = self.current_target
        return await target.url

    @property
    async def page_source(self) -> str:
        """Gets the docs_source of the current page.

        :Usage:
            ::

                target.page_source
        """
        target = self.current_target
        return await target.page_source

    async def close(self, timeout: float = 2) -> None:
        """Closes the current window.

        :Usage:
            ::

                target.close()
        """
        await self.current_target.close(timeout=timeout)

    async def focus(self):
        await self.current_target.focus()

    async def quit(self, timeout: float = 30, start_monotonic: float = None) -> None:
        """Quits the target and closes every associated window.

        :Usage:
            ::

                target.quit()
        """
        from selenium_driverless import EXC_HANDLER
        if not start_monotonic:
            start_monotonic = time.perf_counter()
        # noinspection PyBroadException
        try:
            if self.context_id and self._is_remote:
                # noinspection PyUnresolvedReferences,PyBroadException
                try:
                    await self.base_target.execute_cdp_cmd("Target.disposeBrowserContext",
                                                           {"browserContextId": self.context_id})
                except websockets.exceptions.ConnectionClosedError:
                    pass
                except Exception as e:
                    import sys
                    EXC_HANDLER(e)
            else:
                targets = await self.targets
                for target in list(targets.values()):
                    # noinspection PyUnresolvedReferences
                    try:
                        target = target.Target
                        await target.close(timeout=7)
                        check_timeout(start_monotonic, timeout)
                    except websockets.exceptions.InvalidStatusCode:
                        # already closed
                        pass
                    except ConnectionAbortedError:
                        pass
            for callback in self._closed_callbacks:
                res = callback()
                if inspect.isawaitable(res):
                    await res
        except Exception as e:
            EXC_HANDLER(e)

    @property
    async def current_target_info(self):
        target = self.current_target
        return await target.info

    @property
    def current_window_handle(self) -> str:
        """Returns the current target_id
        """
        return self.current_target.id

    @property
    async def current_window_id(self):
        result = await self.execute_cdp_cmd("Browser.getWindowForTarget", {"targetId": self.current_window_handle})
        return result["windowId"]

    @property
    def context_id(self):
        return self._context_id

    @property
    async def window_handles(self) -> List[TargetInfo]:
        """Returns the handles of all windows within the current session."""
        warnings.warn("window_handles aren't ordered")
        tabs = []
        targets = await self.targets
        for info in list(targets.values()):
            if info.type == "page":
                tabs.append(info)
        return tabs

    async def new_window(self, type_hint: typing.Literal["tab", "window"] = "tab", url="", activate: bool = False,
                         focus: bool = True, background: bool = True) -> Target:
        """creates a new tab or window

        :param type_hint: what kind of target to create
        :param url: url to start the target at
        :param activate: whether to bring the target to the front
        :param focus: whether to emulate focus on the target
        :param background: whether to start the target in the background
        """
        if self._is_incognito and url in ["chrome://extensions"]:
            raise ValueError(f"{url} only supported in non-incognito contexts")

        args = {"url": url}
        if type_hint == "window":
            args["newWindow"] = True
        elif type_hint == "tab":
            pass
        else:
            raise ValueError("type hint needs to be 'window' or 'tab'")
        if not (background is None):
            args["background"] = background

        # noinspection PyProtectedMember
        if self._context_id and self._is_incognito:
            args["browserContextId"] = self._context_id
        target = await self.base_target.execute_cdp_cmd("Target.createTarget", args)
        target_id = target["targetId"]
        target = await self.get_target(target_id)
        if activate:
            await target.activate()
        if focus:
            await target.focus()
        return target

    async def set_window_state(self, state):
        states = ["normal", "minimized", "maximized", "fullscreen"]
        if state not in states:
            raise ValueError(f"expected one of {states}, but got: {state}")
        window_id = await self.current_window_id
        bounds = {"windowState": state}
        await self.execute_cdp_cmd("Browser.setWindowBounds", {"bounds": bounds, "windowId": window_id})

    async def normalize_window(self):
        await self.set_window_state("normal")

    async def maximize_window(self) -> None:
        """Maximizes the current window that webdriver is using."""
        await self.set_window_state("maximized")

    async def fullscreen_window(self) -> None:
        """Invokes the window manager-specific 'full screen' operation."""
        await self.set_window_state("fullscreen")

    async def minimize_window(self) -> None:
        """Invokes the window manager-specific 'minimize' operation."""
        await self.set_window_state("minimized")

    # noinspection PyUnusedLocal
    async def print_page(self) -> str:
        """Takes PDF of the current page.

        The target makes the best effort to return a PDF based on the
        provided parameters.
        """
        target = self.current_target
        return await target.print_page()

    @property
    def switch_to(self) -> SwitchTo:
        """
        :Returns:
            - SwitchTo: an object containing all options to switch focus into

        :Usage:
            ::

                element = target.switch_to.active_element
                alert = target.switch_to.alert
                target.switch_to.default_content()
                target.switch_to.frame('frame_name')
                target.switch_to.frame(1)
                target.switch_to.frame(target.find_elements(By.TAG_NAME, "iframe")[0])
                target.switch_to.parent_frame()
                target.switch_to.window('main')
        """
        return self._switch_to

    # Navigation
    async def back(self) -> None:
        """Goes one step backward in the browser history.
        """
        await self.current_target.back()

    async def forward(self) -> None:
        """Goes one step forward in the browser history.
        """
        await self.current_target.forward()

    async def refresh(self) -> None:
        """Refreshes the current page
        """
        await self.current_target.refresh()

    # Options
    async def get_cookies(self) -> List[dict]:
        """Returns a set of dictionaries, corresponding to cookies visible in
        the current target.
        """
        return await self.current_target.get_cookies()

    async def get_cookie(self, name) -> typing.Optional[typing.Dict]:
        """Get a single cookie by name. Returns the cookie if found, None if
        not.
        """
        return await self.current_target.get_cookie(name=name)

    async def delete_cookie(self, name: str, url: str = None, domain: str = None,
                            path: str = None) -> None:
        """Deletes a single cookie with the given name.
        """
        return await self.current_target.delete_cookie(name=name, url=url, domain=domain, path=path)

    async def delete_all_cookies(self, ) -> None:
        """Delete all cookies in the scope of the session.
        """
        await self.current_target.delete_all_cookies()

    # noinspection GrazieInspection
    async def add_cookie(self, cookie_dict: dict) -> None:
        """Adds a cookie to your current session.

        :param cookie_dict: A dictionary object, with required keys - "name" and "value";
            optional keys - "path", "domain", "secure", "httpOnly", "expiry", "sameSite"

        :Usage:
            ::

                target.add_cookie({'name' : 'foo', 'value' : 'bar'})
                target.add_cookie({'name' : 'foo', 'value' : 'bar', 'path' : '/'})
                target.add_cookie({'name' : 'foo', 'value' : 'bar', 'path' : '/', 'secure' : True})
                target.add_cookie({'name' : 'foo', 'value' : 'bar', 'sameSite' : 'Strict'})
        """
        await self.current_target.add_cookie(cookie_dict=cookie_dict)

    # Timeouts
    @staticmethod
    async def sleep(time_to_wait: float) -> None:
        await asyncio.sleep(time_to_wait)

    # noinspection PyUnusedLocal
    async def find_element(self, by: str, value: str, timeout: float or None = None) -> WebElement:
        """find an element in the current target

        :param by: one of the locators at :func:`By <selenium_driverless.types.by.By>`
        :param value: the actual query to find the element by
        :param timeout: how long to wait for the element to exist
        """
        target = await self.get_target()
        return await target.find_element(by=by, value=value, timeout=timeout)

    async def find_elements(self, by: str, value: str, timeout: float = 3) -> typing.List[WebElement]:
        """find multiple elements in the current target

        :param by: one of the locators at :func:`By <selenium_driverless.types.by.By>`
        :param value: the actual query to find the elements by
        :param timeout: how long to wait for not being in a page reload loop in seconds
        """
        target = await self.get_target()
        return await target.find_elements(by=by, value=value, timeout=timeout)

    async def search_elements(self, query: str) -> typing.List[WebElement]:
        """
        query:str | Plain text or query selector or XPath search query.
        """
        return await self.current_target.search_elements(query=query)

    async def get_screenshot_as_file(self, filename: str) -> None:
        """Saves a screenshot of the current window to a PNG image file.

        :param filename: The full path you wish to save your screenshot to. This
                   should end with a `.png` extension.
        """
        return await self.current_target.get_screenshot_as_file(filename=filename)

    async def save_screenshot(self, filename) -> None:
        """alias to :func: `driver.get_screenshot_as_file <selenium_driverless.webdriver.Chrome.get_screenshot_as_file>`"""
        return await self.current_target.save_screenshot(filename=filename)

    async def get_screenshot_as_png(self) -> bytes:
        """Gets the screenshot of the current window as a binary data.

        :Usage:
            ::

                target.get_screenshot_as_png()
        """
        return await self.current_target.get_screenshot_as_png()

    async def snapshot(self) -> str:
        """gets the current snapshot as mhtml"""
        return await self.current_target.snapshot()

    async def save_snapshot(self, filename: str):
        """Saves a snapshot of the current window to a MHTML file.

        :param filename: The full path you wish to save your snapshot to. This
                   should end with a ``.mhtml`` extension.

        .. code-block:: Python

            await driver.get_snapshot('snapshot.mhtml')

        """
        return await self.current_target.save_snapshot(filename)

    # noinspection PyPep8Naming
    async def set_window_size(self, width, height, windowHandle: str = "current") -> None:
        """Sets the width and height of the current window. (window.resizeTo)

        :Args:
         - width: the width in pixels to set the window to
         - height: the height in pixels to set the window to

        :Usage:
            ::

                target.set_window_size(800,600)
        """
        if windowHandle != "current":
            warnings.warn("Only 'current' window is supported for W3C compatible browsers.")
        await self.set_window_rect(width=int(width), height=int(height))

    # noinspection PyPep8Naming
    async def get_window_size(self) -> dict:
        """Gets the width and height of the current window."""
        size = await self.get_window_rect()

        if size.get("value", None):
            size = size["value"]

        return {k: size[k] for k in ("width", "height")}

    # noinspection PyPep8Naming
    async def set_window_position(self, x, y, windowHandle: str = "current") -> dict:
        """Sets the x,y position of the current window. (window.moveTo)

        :Args:
         - x: the x-coordinate in pixels to set the window position
         - y: the y-coordinate in pixels to set the window position

        :Usage:
            ::

                target.set_window_position(0,0)
        """
        if windowHandle != "current":
            warnings.warn("Only 'current' window is supported for W3C compatible browsers.")
        return await self.set_window_rect(x=int(x), y=int(y))

    # noinspection PyPep8Naming
    async def get_window_position(self, windowHandle="current") -> dict:
        """Gets the x,y position of the current window.

        :Usage:
            ::

                target.get_window_position()
        """

        if windowHandle != "current":
            warnings.warn("Only 'current' window is supported for W3C compatible browsers.")
        position = await self.get_window_rect()

        return {k: position[k] for k in ("x", "y")}

    async def get_window_rect(self) -> dict:
        """Gets the x, y coordinates of the window as well as height and width
        of the current window.

        :Usage:
            ::

                target.get_window_rect()
        """
        json = await self.execute_cdp_cmd("Browser.getWindowBounds", {"windowId": await self.current_window_id})
        json = json["bounds"]
        json["x"] = json["left"]
        del json["left"]
        json["y"] = json["top"]
        del json["top"]
        return json

    async def set_window_rect(self, x=None, y=None, width=None, height=None) -> dict:
        """Sets the x, y coordinates of the window as well as height and width
        of the current window. This method is only supported for W3C compatible
        browsers; other browsers should use `set_window_position` and
        `set_window_size`.

        :Usage:
            ::

                target.set_window_rect(x=10, y=10)
                target.set_window_rect(width=100, height=200)
                target.set_window_rect(x=10, y=10, width=100, height=200)
        """

        if (x is None and y is None) and (not height and not width):
            raise ValueError("x and y or height and width need values")

        bounds = {"left": x, "top": y, "width": width, 'height': height}
        await self.execute_cdp_cmd("Browser.setWindowBounds",
                                   {"windowId": await self.current_window_id, "bounds": bounds})
        bounds["x"] = bounds["left"]
        del bounds["left"]
        bounds["y"] = bounds["top"]
        del bounds["top"]

        return bounds

    async def get_network_conditions(self):
        """Gets Chromium network emulation settings.

        :Returns:
            A dict. For example:
            {'latency': 4, 'download_throughput': 2, 'upload_throughput': 2,
            'offline': False}
        """
        return await self.current_target.get_network_conditions()

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
        return await self.current_target.set_network_conditions(offline=offline, latency=latency,
                                                   download_throughput=download_throughput,
                                                   upload_throughput=upload_throughput, connection_type=connection_type)

    async def delete_network_conditions(self) -> None:
        """Resets Chromium network emulation settings."""
        await self.current_target.delete_network_conditions()

    async def set_permissions(self, name: str, value: str, origin: str = None) -> None:
        """Sets Applicable Permission.

        :Args:
         - name: The item to set the permission on.
         - value: The value to set on the item

        :Usage:
            ::

                target.set_permissions('clipboard-read', 'denied')
        """
        settings = ["granted", "denied", "prompt"]
        if value not in settings:
            raise ValueError(f"value needs to be within {settings}, but got {value}")
        args = {"permission": {"name": name}, "setting": value}
        if self.context_id:
            args["browserContextId"] = self.context_id
        if origin:
            args["origin"] = origin
        await self.execute_cdp_cmd("Browser.setPermission", args)

    async def wait_for_cdp(self, event: str, timeout: float or None = None) -> dict:
        """
        wait for an event on the current target
        see :func:`Target.wait_for_cdp <selenium_driverless.types.target.Target.wait_for_cdp>` for reference
        """
        return await self.current_target.wait_for_cdp(event=event, timeout=timeout)

    async def add_cdp_listener(self, event: str, callback: typing.Callable[[dict], any]):
        """
        add a listener for a CDP event on the current target
        see :func:`Target.add_cdp_listener <selenium_driverless.types.target.Target.add_cdp_listener>` for reference
        """
        return await self.current_target.add_cdp_listener(event=event, callback=callback)

    async def remove_cdp_listener(self, event: str, callback: typing.Callable[[dict], any]):
        """
        remove a listener for a CDP event on the current target
        see :func:`Target.remove_cdp_listener <selenium_driverless.types.target.Target.remove_cdp_listener>` for reference
        """
        return await self.current_target.remove_cdp_listener(event=event, callback=callback)

    async def get_cdp_event_iter(self, event: str) -> typing.AsyncIterable[dict]:
        """
        iterate over CDP events on the current target
        see :func:`Target.get_cdp_event_iter <selenium_driverless.types.target.Target.get_cdp_event_iter>` for reference
        """
        return await self.current_target.get_cdp_event_iter(event=event)

    async def execute_cdp_cmd(self, cmd: str, cmd_args: dict or None = None,
                              timeout: float or None = 10) -> dict:
        """Execute Chrome Devtools Protocol command on the current target
        executes it on :class:`Target.execute_cdp_cmd <selenium_driverless.types.base_target.BaseTarget>`
        if ``message:'Not allowed'`` received
        see :func:`Target.execute_cdp_cmd <selenium_driverless.types.target.Target.execute_cdp_cmd>` for reference
        """
        try:
            return await self.current_target.execute_cdp_cmd(cmd=cmd, cmd_args=cmd_args, timeout=timeout)
        except CDPError as e:
            if e.code == -32000 and e.message == 'Not allowed':
                return await self.base_target.execute_cdp_cmd(cmd=cmd, cmd_args=cmd_args, timeout=timeout)

    async def fetch(self, *args, **kwargs) -> dict:
        """
        executes a JS ``fetch`` request within the current target
        see :func:`Target.fetch <selenium_driverless.types.target.Target.fetch>` for reference
        """
        return await self.current_target.fetch(*args, **kwargs)

    async def xhr(self, *args, **kwargs) -> dict:
        """
        executes a JS ``XMLHttpRequest`` request within the current target
        see :func:`Target.fetch <selenium_driverless.types.target.Target.fetch>` for reference
        """
        return await self.current_target.xhr(*args, **kwargs)

    # noinspection PyTypeChecker
    async def get_sinks(self) -> list:
        """
        :Returns: A list of sinks available for Cast.
        """
        return await self.current_target.get_sinks()

    async def get_issue_message(self):
        """
        :Returns: An error message when there is any issue in a Cast session.
        """
        return await self.current_target.get_issue_message()

    async def set_sink_to_use(self, sink_name: str) -> dict:
        """Sets a specific sink, using its name, as a Cast session receiver
        target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        return await self.current_target.set_sink_to_use(sink_name=sink_name)

    async def start_desktop_mirroring(self, sink_name: str) -> dict:
        """Starts a desktop mirroring session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        return await self.current_target.start_desktop_mirroring(sink_name=sink_name)

    async def start_tab_mirroring(self, sink_name: str) -> dict:
        """Starts a tab mirroring session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        return await self.current_target.start_tab_mirroring(sink_name=sink_name)

    async def stop_casting(self, sink_name: str) -> dict:
        """Stops the existing Cast session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to stop the Cast session.
        """
        return await self.current_target.stop_casting(sink_name=sink_name)
