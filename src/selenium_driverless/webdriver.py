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

# modified by kaliiiiiiiiii | Aurin Aegerter

"""The WebDriver implementation."""
import asyncio
import concurrent.futures
import os.path
import subprocess
import typing
import warnings
from contextlib import asynccontextmanager
from importlib import import_module
from typing import List
from typing import Optional

import websockets.exceptions
from cdp_socket.socket import CDPSocket
from selenium.common.exceptions import InvalidArgumentException
from selenium.webdriver.common.print_page_options import PrintOptions
from selenium.webdriver.remote.bidi_connection import BidiConnection

from selenium_driverless.input.pointer import Pointer
from selenium_driverless.types.options import Options as ChromeOptions
from selenium_driverless.scripts.switch_to import SwitchTo
from selenium_driverless.sync.switch_to import SwitchTo as SyncSwitchTo
from selenium_driverless.types.target import Target


class Chrome:
    """Allows you to drive the browser without chromedriver."""

    def __init__(
            self,
            options: ChromeOptions = None
    ) -> None:
        """Creates a new instance of the chrome target. Starts the service and
        then creates new instance of chrome target.

        :Args:
         - options - this takes an instance of ChromeOptions
        """
        self._loop: asyncio.AbstractEventLoop or None = None
        self._base = None
        self.browser_pid: int or None = None
        self._targets: typing.Dict[str, Target] = {}
        self._current_target_id: str or None = None
        if not options:
            options = ChromeOptions()
        if not options.binary_location:
            from selenium_driverless.utils.utils import find_chrome_executable
            options.binary_location = find_chrome_executable()
        if not options.user_data_dir:
            from selenium_driverless.utils.utils import sel_driverless_path
            import uuid
            options.add_argument("--user-data-dir=" + sel_driverless_path() + "files/tmp/" + uuid.uuid4().hex)

        self._options = options
        self._is_remote = True
        self._switch_to = None
        self._is_remote = False

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
        """Creates a new session with the desired capabilities.

        :Args:
         - capabilities - a capabilities dict to start the session with.
        """
        from selenium_driverless.utils.utils import IS_POSIX, read

        if not self._options.debugger_address:
            from selenium_driverless.utils.utils import random_port
            port = random_port()
            self._options._debugger_address = f"127.0.0.1:{port}"
            self._options.add_argument(f"--remote-debugging-port={port}")
        self._options.add_argument("about:blank")
        options = self._options

        # noinspection PyProtectedMember
        self._is_remote = self._options._is_remote

        if not self._is_remote:
            path = options.binary_location
            args = options.arguments
            browser = subprocess.Popen(
                [path, *args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=IS_POSIX,
                shell=False
            )

            host, port = self._options.debugger_address.split(":")
            port = int(port)
            if port == 0:
                path = self._options.user_data_dir + "/DevToolsActivePort"
                while not os.path.isfile(path):
                    await asyncio.sleep(0.1)
                port = int(read(path, sel_root=False).split("\n")[0])
                self._options.debugger_address = f"127.0.0.1:{port}"

        host, port = self._options.debugger_address.split(":")
        port = int(port)
        self._base = await CDPSocket(port=port, host=host, loop=self._loop, timeout=30)
        if not self._is_remote:
            # noinspection PyUnboundLocalVariable
            self.browser_pid = browser.pid
        targets = await self._base.targets
        for target in targets:
            if target["type"] == "page":
                self._current_target_id = target["id"]

        if self._loop:
            self._switch_to = SyncSwitchTo(driver=self, loop=self._loop)
        else:
            self._switch_to = await SwitchTo(driver=self)
        return self

    @property
    async def targets(self) -> typing.Dict[str, Target]:
        target_infos = await self.target_infos
        for target in target_infos:
            target_id = target['targetId']
            await self.get_target(target_id)
        return self._targets

    async def get_target(self, target_id: str = None):
        if not target_id:
            target_id = self._current_target_id
        target: Target = self._targets.get(target_id)
        if not target:
            socket = await self.base.get_socket(sock_id=target_id)
            target: Target = await Target(socket=socket, is_remote=self._is_remote, loop=self._loop, base=self.base)
            self._targets[target_id] = target

            # noinspection PyUnusedLocal
            def remove_target(code: str, reason: str):
                del self._targets[target_id]

            target.socket.on_closed.append(remove_target)
        return target

    @property
    async def current_target(self) -> Target:
        return await self.get_target()

    async def get(self, url: str, referrer: str = None, wait_load: bool = True, timeout: float = 30) -> None:
        """Loads a web page in the current browser session."""
        target = await self.current_target
        await target.get(url=url, referrer=referrer, wait_load=wait_load, timeout=timeout)

    @property
    async def title(self) -> str:
        """Returns the title of the current target"""
        target = await self.current_target_info
        return target["title"]

    @property
    async def current_pointer(self) -> Pointer:
        target = await self.current_target
        return target.pointer

    async def execute_raw_script(self, script: str, *args, await_res: bool = False, serialization: str = None,
                                 max_depth: int = None, timeout: int = 2, obj_id=None, warn: bool = False,
                                 target_id: str = None):
        """
        example:
        script= "function(...arguments){this.click()}"
        "this" will be the element object
        """
        target = await self.get_target(target_id)
        return await target.execute_raw_script(script, *args, await_res=await_res,
                                               serialization=serialization, max_depth=max_depth,
                                               timeout=timeout, obj_id=obj_id, warn=warn)

    async def execute_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                             timeout: int = None, only_value=True, obj_id=None, warn: bool = False,
                             target_id: str = None):
        """
        exaple: script = "return elem.click()"
        """
        target = await self.get_target(target_id)
        return await target.execute_script(script, *args, max_depth=max_depth, serialization=serialization,
                                           timeout=timeout, only_value=only_value, obj_id=obj_id, warn=warn)

    async def execute_async_script(self, script: str, *args, max_depth: int = 2,
                                   serialization: str = None, timeout: int = 2,
                                   only_value=True, obj_id=None, warn: bool = False,
                                   target_id: str = None):
        target = await self.get_target(target_id)
        return await target.execute_async_script(script, *args, max_depth=max_depth, serialization=serialization,
                                                 timeout=timeout, only_value=only_value, obj_id=obj_id, warn=warn)

    @property
    async def current_url(self) -> str:
        """Gets the URL of the current page.

        :Usage:
            ::

                target.current_url
        """
        target = await self.current_target
        return await target.url

    @property
    async def page_source(self) -> str:
        """Gets the source of the current page.

        :Usage:
            ::

                target.page_source
        """
        target = await self.current_target
        return await target.page_source

    async def close(self, timeout: float = 2, target_id: str = None) -> None:
        """Closes the current window.

        :Usage:
            ::

                target.close()
        """
        if not target_id:
            target_id = self.current_window_handle
        target = await self.get_target(target_id)
        await target.close(timeout=timeout)

    async def focus(self, target_id: str = None):
        target = await self.get_target(target_id)
        await target.focus()

    async def quit(self) -> None:
        """Quits the target and closes every associated window.

        :Usage:
            ::

                target.quit()
        """
        try:
            targets = await self.targets
            for target in list(targets.values()):
                await target.close(timeout=2)
        except TimeoutError:
            pass
        except concurrent.futures.TimeoutError:
            pass
        except websockets.exceptions.ConnectionClosedError:
            pass
        if not self._is_remote:
            import os
            import shutil
            # noinspection PyBroadException,PyUnusedLocal
            try:
                # wait for process to be killed
                while True:
                    try:
                        os.kill(self.browser_pid, 15)
                    except OSError:
                        break
                    await asyncio.sleep(0.1)

                shutil.rmtree(self._options.user_data_dir, ignore_errors=True)
            except Exception as e:
                # We don't care about the message because something probably has gone wrong
                pass
            finally:
                pass

    @property
    async def target_infos(self) -> dict:
        res = await self.execute_cdp_cmd("Target.getTargets")
        return res["targetInfos"]

    @property
    async def current_target_info(self):
        target = await self.current_target
        return await target.info

    @property
    def current_window_handle(self) -> str:
        """Returns the current target_id
        """
        return self._current_target_id

    @property
    async def current_window_id(self):
        result = await self.execute_cdp_cmd("Browser.getWindowForTarget", {"targetId": self.current_window_handle})
        return result["windowId"]

    @property
    async def window_handles(self) -> List[str]:
        """Returns the handles of all windows within the current session.

        :Usage:
            ::

                target.window_handles
        """
        warnings.warn("window_handles aren't ordered")
        tabs = []
        for target in await self.target_infos:
            if target["type"] == "page":
                tabs.append(target['targetId'])
        return tabs

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
        await self.set_window_state("maximized")

    # noinspection PyUnusedLocal
    async def print_page(self, print_options: Optional[PrintOptions] = None) -> str:
        """Takes PDF of the current page.

        The target makes the best effort to return a PDF based on the
        provided parameters.
        """
        target = await self.current_target
        return await target.print_page(print_options=print_options)

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
    async def back(self, target_id: str = None) -> None:
        """Goes one step backward in the browser history.

        :Usage:
            ::

                target.back()
        """
        target = await self.get_target(target_id=target_id)
        await target.back()

    async def forward(self, target_id: str = None) -> None:
        """Goes one step forward in the browser history.

        :Usage:
            ::

                target.forward()
        """
        target = await self.get_target(target_id=target_id)
        await target.forward()

    async def refresh(self, target_id: str = None) -> None:
        """Refreshes the current page.

        :Usage:
            ::

                target.refresh()
        """
        target = await self.get_target(target_id=target_id)
        await target.refresh()

    # Options
    async def get_cookies(self, target_id: str = None) -> List[dict]:
        """Returns a set of dictionaries, corresponding to cookies visible in
        the current target.
        """
        target = await self.get_target(target_id=target_id)
        return await target.get_cookies()

    async def get_cookie(self, name, target_id: str = None) -> typing.Optional[typing.Dict]:
        """Get a single cookie by name. Returns the cookie if found, None if
        not.

        :Usage:
            ::

                target.get_cookie('my_cookie')
        """
        target = await self.get_target(target_id=target_id)
        return await target.get_cookie(name=name)

    async def delete_cookie(self, name: str, url: str = None, domain: str = None,
                            path: str = None, target_id: str = None) -> None:
        """Deletes a single cookie with the given name.
        """
        target = await self.get_target(target_id=target_id)
        return await target.delete_cookie(name=name, url=url, domain=domain, path=path)

    async def delete_all_cookies(self, target_id: str = None) -> None:
        """Delete all cookies in the scope of the session.

        :Usage:
            ::

                target.delete_all_cookies()
        """
        target = await self.get_target(target_id=target_id)
        await target.delete_all_cookies()

    # noinspection GrazieInspection
    async def add_cookie(self, cookie_dict: dict, target_id: str = None) -> None:
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
        target = await self.get_target(target_id=target_id)
        await target.add_cookie(cookie_dict=cookie_dict)

    # Timeouts
    async def sleep(self, time_to_wait: float) -> None:
        await asyncio.sleep(time_to_wait)

    # noinspection PyUnusedLocal
    async def find_element(self, by: str, value: str, parent=None, target_id: str = None):
        target = await self.get_target(target_id=target_id)
        return await target.find_element(by=by, value=value, parent=parent)

    async def find_elements(self, by: str, value: str, parent=None, target_id: str = None):
        target = await self.get_target(target_id=target_id)
        return await target.find_elements(by=by, value=value, parent=parent)

    async def search_elements(self, query: str, target_id: str = None):
        """
        query:str | Plain text or query selector or XPath search query.
        """
        target = await self.get_target(target_id=target_id)
        return await target.search_elements(query=query)

    async def get_screenshot_as_file(self, filename: str, target_id: str = None) -> bool:
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
        target = await self.get_target(target_id=target_id)
        return await target.get_screenshot_as_file(filename=filename)

    async def save_screenshot(self, filename, target_id: str = None) -> bool:
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
        target = await self.get_target(target_id=target_id)
        return await target.save_screenshot(filename=filename)

    async def get_screenshot_as_png(self, target_id: str = None) -> bytes:
        """Gets the screenshot of the current window as a binary data.

        :Usage:
            ::

                target.get_screenshot_as_png()
        """
        target = await self.get_target(target_id=target_id)
        return await target.get_screenshot_as_png()

    async def get_screenshot_as_base64(self, target_id: str = None) -> str:
        """Gets the screenshot of the current window as a base64 encoded string
        which is useful in embedded images in HTML.

        :Usage:
            ::

                target.get_screenshot_as_base64()
        """
        target = await self.get_target(target_id=target_id)
        return await target.get_screenshot_as_base64()

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
    async def get_window_size(self, windowHandle: str = "current") -> dict:
        """Gets the width and height of the current window.

        :Usage:
            ::

                target.get_window_size()
        """

        if windowHandle != "current":
            warnings.warn("Only 'current' window is supported for W3C compatible browsers.")
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
            raise InvalidArgumentException("x and y or height and width need values")

        bounds = {"left": x, "top": y, "width": width, 'height': height}
        await self.execute_cdp_cmd("Browser.setWindowBounds",
                                   {"windowId": await self.current_window_id, "bounds": bounds})
        bounds["x"] = bounds["left"]
        del bounds["left"]
        bounds["y"] = bounds["top"]
        del bounds["top"]

        return bounds

    @asynccontextmanager
    async def bidi_connection(self):
        warnings.warn("bidi connection for driverless is deprecated, use the direct API's instead", DeprecationWarning)
        cdp = import_module("selenium.webdriver.common.bidi.cdp")

        version, ws_url = self._get_cdp_details()

        devtools = cdp.import_devtools(version)
        async with cdp.open_cdp(ws_url) as conn:
            targets = await conn.execute(devtools.target.get_targets())
            target_id = targets[0].target_id
            async with conn.open_session(target_id) as session:
                yield BidiConnection(session, cdp, devtools)

    def _get_cdp_details(self):
        import json

        import urllib3

        http = urllib3.PoolManager()
        debugger_address = self.base.host
        res = http.request("GET", f"http://{debugger_address}/json/version")
        data = json.loads(res.data)

        browser_version = data.get("Browser")
        websocket_url = data.get("webSocketDebuggerUrl")

        import re

        version = re.search(r".*/(\d+)\.", browser_version).group(1)

        return version, websocket_url

    async def get_network_conditions(self, target_id: str = None):
        """Gets Chromium network emulation settings.

        :Returns:
            A dict. For example:
            {'latency': 4, 'download_throughput': 2, 'upload_throughput': 2,
            'offline': False}
        """
        target = await self.get_target(target_id=target_id)
        return await target.get_network_conditions()

    async def set_network_conditions(self, offline: bool, latency: int, download_throughput: int,
                                     upload_throughput: int, connection_type: None, target_id: str = None) -> None:
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
        target = await self.get_target(target_id=target_id)
        return await target.set_network_conditions(offline=offline, latency=latency,
                                                   download_throughput=download_throughput,
                                                   upload_throughput=upload_throughput, connection_type=connection_type)

    async def delete_network_conditions(self, target_id: str = None) -> None:
        """Resets Chromium network emulation settings."""
        target = await self.get_target(target_id=target_id)
        await target.delete_network_conditions()

    async def set_permissions(self, name: str, value: str, origin: str = None, target_id: str = None) -> None:
        """Sets Applicable Permission.

        :Args:
         - name: The item to set the permission on.
         - value: The value to set on the item

        :Usage:
            ::

                target.set_permissions('clipboard-read', 'denied')
        """
        target = await self.get_target(target_id=target_id)
        await target.set_permissions(name=name, value=value, origin=origin)

    @property
    def base(self) -> CDPSocket:
        return self._base

    async def wait_for_cdp(self, event: str, timeout: float or None = None, target_id: str = None):
        target = await self.get_target(target_id=target_id)
        return await target.wait_for_cdp(event=event, timeout=timeout)

    async def add_cdp_listener(self, event: str, callback: callable, target_id: str = None):
        target = await self.get_target(target_id=target_id)
        return await target.add_cdp_listener(event=event, callback=callback)

    async def remove_cdp_listener(self, event: str, callback: callable, target_id: str = None):
        target = await self.get_target(target_id=target_id)
        return await target.remove_cdp_listener(event=event, callback=callback)

    async def get_cdp_event_iter(self, event: str, target_id: str = None):
        target = await self.get_target(target_id=target_id)
        return await target.get_cdp_event_iter(event=event)

    async def execute_cdp_cmd(self, cmd: str, cmd_args: dict or None = None,
                              timeout: float or None = 10, target_id: str = None) -> dict:
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

        target = await self.get_target(target_id=target_id)
        return await target.execute_cdp_cmd(cmd=cmd, cmd_args=cmd_args, timeout=timeout)

    # noinspection PyTypeChecker
    async def get_sinks(self, target_id: str = None) -> list:
        """
        :Returns: A list of sinks available for Cast.
        """
        target = await self.get_target(target_id=target_id)
        return await target.get_sinks()

    async def get_issue_message(self, target_id: str = None):
        """
        :Returns: An error message when there is any issue in a Cast session.
        """
        target = await self.get_target(target_id=target_id)
        return await target.get_issue_message()

    async def set_sink_to_use(self, sink_name: str, target_id: str = None) -> dict:
        """Sets a specific sink, using its name, as a Cast session receiver
        target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        target = await self.get_target(target_id=target_id)
        return await target.set_sink_to_use(sink_name=sink_name)

    async def start_desktop_mirroring(self, sink_name: str, target_id: str = None) -> dict:
        """Starts a desktop mirroring session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        target = await self.get_target(target_id=target_id)
        return await target.start_desktop_mirroring(sink_name=sink_name)

    async def start_tab_mirroring(self, sink_name: str, target_id: str = None) -> dict:
        """Starts a tab mirroring session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        target = await self.get_target(target_id=target_id)
        return await target.start_tab_mirroring(sink_name=sink_name)

    async def stop_casting(self, sink_name: str, target_id: str = None) -> dict:
        """Stops the existing Cast session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to stop the Cast session.
        """
        target = await self.get_target(target_id=target_id)
        return await target.stop_casting(sink_name=sink_name)
