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
import os.path
import subprocess
import typing
import warnings
from abc import ABCMeta
from base64 import b64decode
from base64 import urlsafe_b64encode
from contextlib import asynccontextmanager
from importlib import import_module
from typing import List
from typing import Optional
from typing import Union

from selenium.common.exceptions import InvalidArgumentException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.print_page_options import PrintOptions
from selenium.webdriver.common.virtual_authenticator import Credential
from selenium.webdriver.common.virtual_authenticator import VirtualAuthenticatorOptions
from selenium.webdriver.common.virtual_authenticator import (
    required_virtual_authenticator,
)
from selenium.webdriver.remote.bidi_connection import BidiConnection
from selenium.webdriver.remote.file_detector import FileDetector
from selenium.webdriver.remote.file_detector import LocalFileDetector
from selenium.webdriver.remote.mobile import Mobile
from selenium.webdriver.remote.script_key import ScriptKey
from selenium.webdriver.remote.webdriver import create_matches

from selenium_driverless.scripts.options import Options as ChromeOptions
from selenium_driverless.scripts.switch_to import SwitchTo
from selenium_driverless.sync.switch_to import SwitchTo as SyncSwitchTo
from selenium_driverless.types.webelement import WebElement, RemoteObject
from selenium_driverless.sync.webelement import WebElement as SyncWebElement

from cdp_socket.socket import CDPSocket, SingleCDPSocket


def import_cdp():
    return import_module("selenium.webdriver.common.bidi.cdp")


class BaseWebDriver(metaclass=ABCMeta):
    """Abstract Base Class for all Webdriver subtypes.

    ABC's allow custom implementations of Webdriver to be registered so
    that isinstance type checks will succeed.
    """


class Chrome(BaseWebDriver):
    """Allows you to drive the browser without chromedriver."""

    def __init__(
            self,
            options: ChromeOptions = None,
            disconnect_connect=False
    ) -> None:
        """Creates a new instance of the chrome driver. Starts the service and
        then creates new instance of chrome driver.

        :Args:
         - options - this takes an instance of ChromeOptions
        """
        if disconnect_connect:
            warnings.warn("disconnect_connect=True might be buggy")
        self._page_enabled = None

        self._global_this = None
        self._document_node_id_ = None

        self._loop: asyncio.AbstractEventLoop or None = None
        self._page_load_timeout: int = 30
        self._script_timeout: int = 30
        self._base = None
        self.browser_pid: int or None = None
        self._targets: list = []
        self._current_target: str or None = None
        self._disconnect_connect: bool = disconnect_connect
        if not options:
            options = ChromeOptions()
        if not options.binary_location:
            from selenium_driverless.utils.utils import find_chrome_executable
            options.binary_location = find_chrome_executable()
        if not options.user_data_dir:
            from selenium_driverless.utils.utils import sel_driverless_path
            import uuid
            options.add_argument("--user-data-dir=" + sel_driverless_path() + "/files/tmp/" + uuid.uuid4().hex)

        try:
            self._options = options

            vendor_prefix = "goog"
            self.vendor_prefix = vendor_prefix

            if isinstance(options, list):
                self._capabilities = create_matches(options)
            else:
                self._capabilities = options.to_capabilities()
            self._is_remote = True
            self.caps = {}
            self.pinned_scripts = {}
            self._switch_to = None
            self._mobile = Mobile(self)
            self.file_detector = LocalFileDetector()
            self._authenticator_id = None

        except Exception:
            self.quit()
            raise
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

    @property
    def mobile(self) -> Mobile:
        raise NotImplementedError()
        # return self._mobile

    @property
    def name(self) -> str:
        """Returns the name of the underlying browser for this instance.

        :Usage:
            ::

                name = driver.name
        """
        if "browserName" in self.caps:
            return self.caps["browserName"]
        raise KeyError("browserName not specified in session capabilities")

    async def start_client(self):
        """Called before starting a new session.

        This method may be overridden to define custom startup behavior.
        """
        pass

    async def stop_client(self):
        """Called after executing a quit command.

        This method may be overridden to define custom shutdown
        behavior.
        """
        pass

    async def start_session(self, capabilities: dict or None = None):
        """Creates a new session with the desired capabilities.

        :Args:
         - capabilities - a capabilities dict to start the session with.
        """
        await self.start_client()
        if not capabilities:
            capabilities = self._capabilities
        del self._capabilities
        from selenium_driverless.utils.utils import IS_POSIX, read

        if not self._options.debugger_address:
            from selenium_driverless.utils.utils import random_port
            port = random_port()
            self._options._debugger_address = f"127.0.0.1:{port}"
            self._options.add_argument(f"--remote-debugging-port={port}")
        options = capabilities["goog:chromeOptions"]

        # noinspection PyProtectedMember
        self._is_remote = self._options._is_remote

        if not self._is_remote:
            path = options["binary"]
            args = options["args"]
            cmds = [path, *args]
            browser = subprocess.Popen(
                cmds,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=IS_POSIX,
                shell=IS_POSIX
            )

            host, port = self._options.debugger_address.split(":")
            port = int(port)
            if port == 0:
                path = self._options.user_data_dir + "/DevToolsActivePort"
                while not os.path.isfile(path):
                    await self.implicitly_wait(0.1)
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
                self._current_target = target["id"]
        self._global_this = await RemoteObject(driver=self, js="globalThis", check_existence=False)
        self.caps = capabilities

        if self._loop:
            self._switch_to = SyncSwitchTo(driver=self, loop=self._loop)
        else:
            self._switch_to = await SwitchTo(driver=self)

        # noinspection PyUnusedLocal
        def clear_global_this(data):
            self._global_this = None
            self._document_node_id_ = None

        await self.add_cdp_listener("Page.loadEventFired", clear_global_this)

        return self

    async def create_web_element(self, element_id: str) -> WebElement:
        """Creates a web element with the specified `element_id`."""
        raise NotImplementedError()

    async def execute(self, driver_command: str = None, params: dict = None):
        """
        executes on current pycdp.cdp cmd on current session
        driver_command and params aren't used
        """
        raise NotImplementedError("chrome not started with chromedriver")

    # noinspection PyUnboundLocalVariable
    async def get(self, url: str, referrer: str = None, wait_load: bool = True,
                  disconnect_connect: bool = None) -> None:
        """Loads a web page in the current browser session."""
        if url == "about:blank":
            wait_load = False
        loop = self._loop
        if not loop:
            loop = asyncio.get_running_loop()
        if wait_load:
            await self.execute_cdp_cmd("Page.enable", disconnect_connect=False)
            wait = loop.create_task(self.wait_for_cdp("Page.loadEventFired", timeout=self._page_load_timeout))
        args = {"url": url, "transitionType": "link"}
        if referrer:
            args["referrer"] = referrer
        _disconnect = None
        if disconnect_connect is False:
            _disconnect = False
        get = loop.create_task(self.execute_cdp_cmd("Page.navigate", args, disconnect_connect=_disconnect))
        if wait_load:
            try:
                await wait
            except asyncio.TimeoutError:
                raise TimeoutError(f"page didn't load within timeout of {self._page_load_timeout}")
        await get
        self._global_this = None
        self._document_node_id_ = None

    @property
    async def title(self) -> str:
        # noinspection GrazieInspection
        """Returns the title of the current page.

                :Usage:
                    ::

                        title = driver.title
                """
        target = await self.current_target
        return target["title"]

    def pin_script(self, script: str, script_key=None) -> ScriptKey:
        """Store common javascript scripts to be executed later by a unique
        hashable ID."""
        script_key_instance = ScriptKey(script_key)
        self.pinned_scripts[script_key_instance.id] = script
        return script_key_instance

    def unpin(self, script_key: ScriptKey) -> None:
        """Remove a pinned script from storage."""
        try:
            self.pinned_scripts.pop(script_key.id)
        except KeyError:
            raise KeyError(f"No script with key: {script_key} existed in {self.pinned_scripts}") from None

    def get_pinned_scripts(self) -> List[str]:
        return list(self.pinned_scripts)

    async def _parse_res(self, res):
        if "subtype" in res.keys():
            if res["subtype"] == 'node':
                if self._loop:
                    res["value"] = await SyncWebElement(driver=self, loop=self._loop,
                                                        obj_id=res["objectId"],
                                                        check_existence=False)
                else:
                    res["value"] = await WebElement(driver=self, obj_id=res["objectId"],
                                                    check_existence=False)
        if 'className' in res.keys():
            class_name = res['className']
            if class_name in ['NodeList', 'HTMLCollection']:
                elems = []
                obj = await RemoteObject(driver=self, obj_id=res["objectId"], check_existence=False)
                for idx in range(int(res['description'][-2])):
                    elems.append(await obj.execute_script("return this[arguments[0]]", idx, serialization="deep"))
                res["value"] = elems
            elif class_name == 'XPathResult':
                elems = []
                obj = await RemoteObject(driver=self, obj_id=res["objectId"], check_existence=False)
                if await obj.execute_script("return [7].includes(this.resultType)", serialization="json"):
                    for idx in range(await obj.execute_script("return this.snapshotLength", serialization="json")):
                        elems.append(await obj.execute_script("return this.snapshotItem(arguments[0])", idx,
                                                              serialization="deep"))
                    res["value"] = elems
        return res

    async def execute_raw_script(self, script: str, *args, await_res: bool = False, serialization: str = None,
                                 max_depth: int = None, timeout: int = 2, obj_id=None, warn: bool = False):
        """
        example:
        script= "function(...arguments){this.click()}"
        "this" will be the element object
        """
        from selenium_driverless.types import RemoteObject, JSEvalException
        if warn:
            warnings.warn("execute_script might be detected", stacklevel=4)
        if not obj_id:
            if not self._global_this:
                self._global_this = await RemoteObject(driver=self, js="globalThis", check_existence=False)
            obj_id = await self._global_this.obj_id
        if not timeout:
            timeout = self._script_timeout
        if not args:
            args = []
        if not serialization:
            serialization = "deep"
        _args = []
        for arg in args:
            if isinstance(arg, RemoteObject):
                _args.append({"objectId": await arg.obj_id})
            else:
                _args.append({"value": arg})

        ser_opts = {"serialization": serialization, "maxDepth": max_depth,
                    "additionalParameters": {"includeShadowTree": "all", "maxNodeDepth": max_depth}}
        args = {"functionDeclaration": script, "objectId": obj_id,
                "arguments": _args, "userGesture": True, "awaitPromise": await_res, "serializationOptions": ser_opts}
        res = await asyncio.wait_for(self.execute_cdp_cmd("Runtime.callFunctionOn", args), timeout=timeout)
        if "exceptionDetails" in res.keys():
            raise JSEvalException(res["exceptionDetails"])
        res = res["result"]
        res = await self._parse_res(res)
        return res

    async def execute_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                             timeout: int = None,
                             only_value=True, obj_id=None, warn: bool = False):
        """
        exaple: script = "return elem.click()"
        """
        script = f"(function(...arguments){{{script}}})"
        res = await self.execute_raw_script(script, *args, max_depth=max_depth,
                                            serialization=serialization, timeout=timeout,
                                            await_res=False, obj_id=obj_id, warn=warn)
        if only_value:
            if "value" in res.keys():
                return res["value"]
        else:
            return res

    async def execute_async_script(self, script: str, *args, max_depth: int = 2,
                                   serialization: str = None, timeout: int = 2,
                                   only_value=True, obj_id=None, warn: bool = False):
        script = """(function(...arguments){
                       const promise = new Promise((resolve, reject) => {
                              arguments.push(resolve)
                        });""" + script + ";return promise})"
        res = await self.execute_raw_script(script, *args, max_depth=max_depth,
                                            serialization=serialization, timeout=timeout,
                                            await_res=True, obj_id=obj_id, warn=warn)
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

                driver.current_url
        """
        target = await self.current_target
        return target["url"]

    @property
    async def page_source(self) -> str:
        """Gets the source of the current page.

        :Usage:
            ::

                driver.page_source
        """
        return await self.execute_script("return document.documentElement.outerHTML")

    async def close(self, timeout:float=2) -> None:
        """Closes the current window.

        :Usage:
            ::

                driver.close()
        """
        from warnings import simplefilter
        simplefilter("ignore", UserWarning)
        window_handles = await self.window_handles
        simplefilter("always", UserWarning)
        await self.execute_cdp_cmd("Page.close", timeout=timeout)
        await self.switch_to.window(window_handles[0])

    async def quit(self) -> None:
        """Quits the driver and closes every associated window.

        :Usage:
            ::

                driver.quit()
        """
        if not self._is_remote:
            import os
            import shutil
            # noinspection PyBroadException,PyUnusedLocal
            try:
                try:
                    await self.close()
                    # wait for process to be killed
                    while True:
                        try:
                            os.kill(self.browser_pid, 15)
                        except OSError:
                            break
                        await self.implicitly_wait(0.1)

                    shutil.rmtree(self._options.user_data_dir, ignore_errors=True)
                finally:
                    await self.stop_client()
            except Exception as e:
                # We don't care about the message because something probably has gone wrong
                pass
            finally:
                pass  # self.service.stop()

    @property
    async def targets(self) -> dict:
        res = await self.execute_cdp_cmd("Target.getTargets")
        return res["targetInfos"]

    @property
    async def current_target(self):
        res = await self.execute_cdp_cmd("Target.getTargetInfo", {"targetId": self.current_window_handle})
        return res["targetInfo"]

    @property
    def current_window_handle(self) -> str:
        """Returns the handle of the current window.

        :Usage:
            ::

                driver.current_window_handle
        """
        # noinspection PyProtectedMember
        return self._current_target

    @property
    async def current_window_id(self):
        result = await self.execute_cdp_cmd("Browser.getWindowForTarget", {"targetId": self.current_window_handle})
        return result["windowId"]

    @property
    async def window_handles(self) -> List[str]:
        """Returns the handles of all windows within the current session.

        :Usage:
            ::

                driver.window_handles
        """
        warnings.warn("window_handles aren't ordered")
        tabs = []
        for target in await self.targets:
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
        await self.normalize_window()
        await self.set_window_state("maximized")

    async def fullscreen_window(self) -> None:
        """Invokes the window manager-specific 'full screen' operation."""
        await self.normalize_window()
        await self.set_window_state("fullscreen")

    async def minimize_window(self) -> None:
        """Invokes the window manager-specific 'minimize' operation."""
        await self.normalize_window()
        await self.set_window_state("maximized")

    # noinspection PyUnusedLocal
    async def print_page(self, print_options: Optional[PrintOptions] = None) -> str:
        """Takes PDF of the current page.

        The driver makes the best effort to return a PDF based on the
        provided parameters.
        """
        options = {}
        if print_options:
            options = print_options.to_dict()
            raise NotImplementedError()

        page = await self.execute_cdp_cmd("Page.printToPDF")
        return page["data"]

    @property
    def switch_to(self) -> SwitchTo:
        """
        :Returns:
            - SwitchTo: an object containing all options to switch focus into

        :Usage:
            ::

                element = driver.switch_to.active_element
                alert = driver.switch_to.alert
                driver.switch_to.default_content()
                driver.switch_to.frame('frame_name')
                driver.switch_to.frame(1)
                driver.switch_to.frame(driver.find_elements(By.TAG_NAME, "iframe")[0])
                driver.switch_to.parent_frame()
                driver.switch_to.window('main')
        """
        return self._switch_to

    @property
    async def _current_history_idx(self):
        res = await self.execute_cdp_cmd("Page.getNavigationHistory")
        return res["currentIndex"]

    # Navigation
    async def back(self) -> None:
        """Goes one step backward in the browser history.

        :Usage:
            ::

                driver.back()
        """
        await self.execute_cdp_cmd("Page.navigateToHistoryEntry", {"entryId": await self._current_history_idx - 1})

    async def forward(self) -> None:
        """Goes one step forward in the browser history.

        :Usage:
            ::

                driver.forward()
        """
        await self.execute_cdp_cmd("Page.navigateToHistoryEntry", {"entryId": await self._current_history_idx + 1})

    async def refresh(self) -> None:
        """Refreshes the current page.

        :Usage:
            ::

                driver.refresh()
        """
        await self.execute_cdp_cmd("Page.reload")

    # Options
    async def get_cookies(self) -> List[dict]:
        """Returns a set of dictionaries, corresponding to cookies visible in
        the current session.

        :Usage:
            ::

                driver.get_cookies()
        """
        cookies = await self.execute_cdp_cmd("Page.getCookies")
        return cookies["cookies"]

    async def get_cookie(self, name) -> typing.Optional[typing.Dict]:
        """Get a single cookie by name. Returns the cookie if found, None if
        not.

        :Usage:
            ::

                driver.get_cookie('my_cookie')
        """
        for cookie in await self.get_cookies():
            if cookie["name"] == name:
                return cookie
        return None

    async def delete_cookie(self, name: str, url: str = None, domain: str = None, path: str = None) -> None:
        """Deletes a single cookie with the given name.

        :Usage:
            ::

                driver.delete_cookie('my_cookie')
        """
        args = {"name": name}
        if url:
            args["url"] = url
        if domain:
            args["domain"] = domain
        if path:
            args["path"] = path
        await self.execute_cdp_cmd("Network.deleteCookies", args)

    async def delete_all_cookies(self) -> None:
        """Delete all cookies in the scope of the session.

        :Usage:
            ::

                driver.delete_all_cookies()
        """
        await self.execute_cdp_cmd("Network.clearBrowserCookies")

    # noinspection GrazieInspection
    async def add_cookie(self, cookie_dict) -> None:
        """Adds a cookie to your current session.

        :Args:
         - cookie_dict: A dictionary object, with required keys - "name" and "value";
            optional keys - "path", "domain", "secure", "httpOnly", "expiry", "sameSite"

        :Usage:
            ::

                driver.add_cookie({'name' : 'foo', 'value' : 'bar'})
                driver.add_cookie({'name' : 'foo', 'value' : 'bar', 'path' : '/'})
                driver.add_cookie({'name' : 'foo', 'value' : 'bar', 'path' : '/', 'secure' : True})
                driver.add_cookie({'name' : 'foo', 'value' : 'bar', 'sameSite' : 'Strict'})
        """
        if "sameSite" in cookie_dict:
            assert cookie_dict["sameSite"] in ["Strict", "Lax", "None"]
        await self.execute_cdp_cmd("Network.setCookie", cookie_dict)

    # Timeouts
    async def implicitly_wait(self, time_to_wait: float) -> None:
        """Sets a sticky timeout to implicitly wait for an element to be found,
        or a command to complete. This method only needs to be called one time
        per session. To set the timeout for calls to execute_async_script, see
        set_script_timeout.

        :Args:
         - time_to_wait: Amount of time to wait (in seconds)

        :Usage:
            ::

                driver.implicitly_wait(30)
        """
        await asyncio.sleep(time_to_wait)

    def set_script_timeout(self, time_to_wait: float) -> None:
        """Set the amount of time that the script should wait during an
        execute_async_script call before throwing an error.

        :Args:
         - time_to_wait: The amount of time to wait (in seconds)

        :Usage:
            ::

                driver.set_script_timeout(30)
        """
        self._script_timeout = time_to_wait

    def set_page_load_timeout(self, time_to_wait: float) -> None:
        """Set the amount of time to wait for a page load to complete before
        throwing an error.

        :Args:
         - time_to_wait: The amount of time to wait

        :Usage:
            ::

                driver.set_page_load_timeout(30)
        """
        self._page_load_timeout = time_to_wait

    @property
    def timeouts(self) -> dict:
        """Get all the timeouts that have been set on the current session.

        :Usage:
            ::

                driver.timeouts
        :rtype: Timeout
        """
        return {"page_load": self._page_load_timeout, "script": self._script_timeout}

    @timeouts.setter
    def timeouts(self, timeouts):
        self._page_load_timeout = timeouts["page_load"]
        self._script_timeout = timeouts["script"]

    @property
    async def _document_node_id(self):
        if not self._document_node_id_:
            res = await self.execute_cdp_cmd("DOM.getDocument", {"pierce": True})
            self._document_node_id_ = res["root"]["nodeId"]
        return self._document_node_id_

    # noinspection PyUnusedLocal
    async def find_element(self, by: str, value: str, parent=None):
        if not parent:
            parent = await WebElement(driver=self, node_id=await self._document_node_id, check_existence=False, loop=self._loop)
        return await parent.find_element(by=by, value=value)

    async def find_elements(self, by: str, value: str, parent=None):
        if not parent:
            parent = await WebElement(driver=self, node_id=await self._document_node_id, check_existence=False, loop=self._loop)
        return await parent.find_elements(by=by, value=value)

    async def search_elements(self, query: str):
        """
        query:str | Plain text or query selector or XPath search query.
        """
        elems = []
        res = await self.execute_cdp_cmd("DOM.performSearch",
                                         {"includeUserAgentShadowDOM": True, "query": query})
        search_id = res["searchId"]
        elem_count = res["resultCount"]

        res = await self.execute_cdp_cmd("DOM.getSearchResults",
                                         {"searchId": search_id, "fromIndex": 0, "toIndex": elem_count - 1})
        for node_id in res["nodeIds"]:
            if self._loop:
                elem = await SyncWebElement(driver=self, check_existence=False, node_id=node_id, loop=self._loop)
            else:
                elem = await WebElement(driver=self, check_existence=False, node_id=node_id, loop=self._loop)
            elems.append(elem)
        return elems

    @property
    def capabilities(self) -> dict:
        """returns the drivers current capabilities being used."""
        return self.caps

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

                        driver.get_screenshot_as_file('/Screenshots/foo.png')
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

                        driver.save_screenshot('/Screenshots/foo.png')
                """
        return await self.get_screenshot_as_file(filename)

    async def get_screenshot_as_png(self) -> bytes:
        """Gets the screenshot of the current window as a binary data.

        :Usage:
            ::

                driver.get_screenshot_as_png()
        """
        base_64 = await self.get_screenshot_as_base64()
        return b64decode(base_64.encode("ascii"))

    async def get_screenshot_as_base64(self) -> str:
        """Gets the screenshot of the current window as a base64 encoded string
        which is useful in embedded images in HTML.

        :Usage:
            ::

                driver.get_screenshot_as_base64()
        """
        res = await self.execute_cdp_cmd("Page.captureScreenshot", {"format": "png"})
        return res["data"]

    # noinspection PyPep8Naming
    async def set_window_size(self, width, height, windowHandle: str = "current") -> None:
        """Sets the width and height of the current window. (window.resizeTo)

        :Args:
         - width: the width in pixels to set the window to
         - height: the height in pixels to set the window to

        :Usage:
            ::

                driver.set_window_size(800,600)
        """
        if windowHandle != "current":
            warnings.warn("Only 'current' window is supported for W3C compatible browsers.")
        await self.set_window_rect(width=int(width), height=int(height))

    # noinspection PyPep8Naming
    async def get_window_size(self, windowHandle: str = "current") -> dict:
        """Gets the width and height of the current window.

        :Usage:
            ::

                driver.get_window_size()
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

                driver.set_window_position(0,0)
        """
        if windowHandle != "current":
            warnings.warn("Only 'current' window is supported for W3C compatible browsers.")
        return await self.set_window_rect(x=int(x), y=int(y))

    # noinspection PyPep8Naming
    async def get_window_position(self, windowHandle="current") -> dict:
        """Gets the x,y position of the current window.

        :Usage:
            ::

                driver.get_window_position()
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

                driver.get_window_rect()
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

                driver.set_window_rect(x=10, y=10)
                driver.set_window_rect(width=100, height=200)
                driver.set_window_rect(x=10, y=10, width=100, height=200)
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

    @property
    def file_detector(self) -> FileDetector:
        return self._file_detector

    @file_detector.setter
    def file_detector(self, detector) -> None:
        """Set the file detector to be used when sending keyboard input. By
        default, this is set to a file detector that does nothing.

        see FileDetector
        see LocalFileDetector
        see UselessFileDetector

        :Args:
         - detector: The detector to use. Must not be None.
        """
        if not detector:
            raise WebDriverException("You may not set a file detector that is null")
        if not isinstance(detector, FileDetector):
            raise WebDriverException("Detector has to be instance of FileDetector")
        self._file_detector = detector

    @property
    def orientation(self):
        # noinspection GrazieInspection
        """Gets the current orientation of the device.

                :Usage:
                    ::

                        orientation = driver.orientation
                """
        raise NotImplementedError()

    @orientation.setter
    def orientation(self, value) -> None:
        """Sets the current orientation of the device.

        :Args:
         - value: orientation to set it to.

        :Usage:
            ::

                driver.orientation = 'landscape'
        """
        allowed_values = ["LANDSCAPE", "PORTRAIT"]
        if value.upper() in allowed_values:
            raise NotImplementedError()
        else:
            raise WebDriverException("You can only set the orientation to 'LANDSCAPE' and 'PORTRAIT'")

    @property
    def log_types(self):
        """Gets a list of the available log types. This only works with w3c
        compliant browsers.

        :Usage:
            ::

                driver.log_types
        """
        raise NotImplementedError("not started with chromedriver")

    def get_log(self, log_type):
        """Gets the log for a given log type.

        :Args:
         - log_type: type of log that which will be returned

        :Usage:
            ::

                driver.get_log('browser')
                driver.get_log('driver')
                driver.get_log('client')
                driver.get_log('server')
        """
        raise NotImplementedError("not started with chromedriver")

    @asynccontextmanager
    async def bidi_connection(self):
        cdp = import_cdp()
        if self.caps.get("se:cdp"):
            ws_url = self.caps.get("se:cdp")
            version = self.caps.get("se:cdpVersion").split(".")[0]
        else:
            version, ws_url = self._get_cdp_details()

        if not ws_url:
            raise WebDriverException("Unable to find url to connect to from capabilities")

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
        debugger_address = self.caps.get("goog:chromeOptions").get("debuggerAddress")
        res = http.request("GET", f"http://{debugger_address}/json/version")
        data = json.loads(res.data)

        browser_version = data.get("Browser")
        websocket_url = data.get("webSocketDebuggerUrl")

        import re

        version = re.search(r".*/(\d+)\.", browser_version).group(1)

        return version, websocket_url

    # Virtual Authenticator Methods
    def add_virtual_authenticator(self, options: VirtualAuthenticatorOptions) -> None:
        """Adds a virtual authenticator with the given options."""
        # self._authenticator_id = self.execute(Command.ADD_VIRTUAL_AUTHENTICATOR, options.to_dict())["value"]
        raise NotImplementedError("not started with chromedriver")

    @property
    def virtual_authenticator_id(self) -> str:
        """Returns the id of the virtual authenticator."""
        raise NotImplementedError("not started with chromedriver")
        # return self._authenticator_id

    @required_virtual_authenticator
    def remove_virtual_authenticator(self) -> None:
        """Removes a previously added virtual authenticator.

        The authenticator is no longer valid after removal, so no
        methods may be called.
        """
        raise NotImplementedError("not started with chromedriver")
        # self._authenticator_id = None

    @required_virtual_authenticator
    def add_credential(self, credential: Credential) -> None:
        """Injects a credential into the authenticator."""
        raise NotImplementedError("not started with chromedriver")

    # noinspection PyTypeChecker
    @required_virtual_authenticator
    def get_credentials(self) -> List[Credential]:
        """Returns the list of credentials owned by the authenticator."""
        # credential_data = self.execute(Command.GET_CREDENTIALS, {"authenticatorId": self._authenticator_id})
        raise NotImplementedError("not started with chromedriver")

    @required_virtual_authenticator
    def remove_credential(self, credential_id: Union[str, bytearray]) -> None:
        """Removes a credential from the authenticator."""
        # Check if the credential is bytearray converted to b64 string
        if isinstance(credential_id, bytearray):
            # noinspection PyUnusedLocal
            credential_id = urlsafe_b64encode(credential_id).decode()

        raise NotImplementedError("not started with chromedriver")

    @required_virtual_authenticator
    def remove_all_credentials(self) -> None:
        """Removes all credentials from the authenticator."""
        raise NotImplementedError("not started with chromedriver")

    @required_virtual_authenticator
    def set_user_verified(self, verified: bool) -> None:
        """Sets whether the authenticator will simulate success or fail on user
        verification.

        verified: True if the authenticator will pass user verification, False otherwise.
        """
        raise NotImplementedError("not started with chromedriver")

    #
    # selenium.webdriver.chrome.WebDriver props from here on
    #

    # noinspection PyShadowingBuiltins
    def launch_app(self, id):
        """Launches Chromium app specified by id."""
        raise NotImplementedError("not started with chromedriver")

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

                driver.set_network_conditions(
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

    def delete_network_conditions(self) -> None:
        """Resets Chromium network emulation settings."""
        raise NotImplementedError("not started with chromedriver")

    async def set_permissions(self, name: str, value: str, origin: str = None) -> None:
        """Sets Applicable Permission.

        :Args:
         - name: The item to set the permission on.
         - value: The value to set on the item

        :Usage:
            ::

                driver.set_permissions('clipboard-read', 'denied')
        """
        settings = ["granted", "denied", "prompt"]
        if value not in settings:
            raise ValueError(f"value needs to be within {settings}, but got {value}")
        args = {"permission": {"name": name}, "setting": value}
        if origin:
            args["origin"] = origin
        await self.execute_cdp_cmd("Browser.setPermission", args)

    @property
    def base(self):
        return self._base

    @property
    def sockets(self):
        return self.base.sockets

    @property
    async def current_socket(self) -> SingleCDPSocket:
        sock_id = self.current_window_handle
        socket = self.sockets[sock_id]
        if not socket:
            socket = await self.base.get_socket(sock_id=sock_id)
        return socket

    async def wait_for_cdp(self, event: str, timeout: float or None = None):
        socket = await self.current_socket
        return await socket.wait_for(event, timeout=timeout)

    async def add_cdp_listener(self, event: str, callback: callable):
        socket = await self.current_socket
        socket.add_listener(method=event, callback=callback)

    async def remove_cdp_listener(self, event: str, callback: callable):
        socket = await self.current_socket
        socket.remove_listener(method=event, callback=callback)

    async def get_cdp_event_iter(self, event: str):
        socket = await self.current_socket
        return socket.method_iterator(method=event)

    async def execute_cdp_cmd(self, cmd: str, cmd_args: dict or None = None, disconnect_connect=None, timeout:float or None=10) -> dict:
        """Execute Chrome Devtools Protocol command and get returned result The
        command and command args should follow chrome devtools protocol
        domains/commands, refer to link
        https://chromedevtools.github.io/devtools-protocol/

        :Args:
         - cmd: A str, command name
         - cmd_args: A dict, command args. empty dict {} if there is no command args
        :Usage:
            ::

                driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': requestId})
        :Returns:
            A dict, empty dict {} if there is no result to return.
            For example to getResponseBody:
            {'base64Encoded': False, 'body': 'response body string'}
        """
        if not disconnect_connect:
            disconnect_connect = self._disconnect_connect

        socket: SingleCDPSocket = await self.current_socket
        result = await socket.exec(method=cmd, params=cmd_args, timeout=timeout)
        if cmd == "Page.enable":
            self._page_enabled = True
        elif cmd == "Page.disable":
            self._page_enabled = False
        if disconnect_connect:
            await socket.close()
            self._page_enabled = False
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
