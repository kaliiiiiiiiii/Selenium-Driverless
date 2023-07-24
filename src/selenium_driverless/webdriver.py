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

import pycdp.cdp.target
from selenium.common.exceptions import InvalidArgumentException
from selenium.common.exceptions import JavascriptException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.print_page_options import PrintOptions
from selenium.webdriver.common.virtual_authenticator import Credential
from selenium.webdriver.common.virtual_authenticator import VirtualAuthenticatorOptions
from selenium.webdriver.common.virtual_authenticator import (
    required_virtual_authenticator,
)
from selenium.webdriver.remote.bidi_connection import BidiConnection
from selenium.webdriver.remote.file_detector import FileDetector
from selenium.webdriver.remote.file_detector import LocalFileDetector
from selenium.webdriver.remote.script_key import ScriptKey
from selenium.webdriver.remote.webdriver import create_matches
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.relative_locator import RelativeBy
from selenium.webdriver.remote.mobile import Mobile

from selenium_driverless.scripts.options import Options
from selenium_driverless.scripts.switch_to import SwitchTo
from selenium_driverless.sync.switch_to import SwitchTo as SyncSwitchTo


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
            options: Options = None,
    ) -> None:
        """Creates a new instance of the chrome driver. Starts the service and
        then creates new instance of chrome driver.

        :Args:
         - options - this takes an instance of ChromeOptions
        """
        self._loop = None
        self._page_load_timeout = 300
        self._script_timeout = 30
        self._conn = None
        self.session = None
        self.browser_pid = None

        try:
            options = options or Options()
            self._options = options

            vendor_prefix = "goog"
            self.vendor_prefix = vendor_prefix

            if isinstance(options, list):
                self._capabilities = create_matches(options)
            else:
                self._capabilities = options.to_capabilities()
            self._is_remote = True
            self.target_id = None
            self.caps = {}
            self.pinned_scripts = {}
            self._switch_to = SwitchTo(self)
            self._mobile = Mobile(self)
            self.file_detector = LocalFileDetector()
            self._authenticator_id = None

        except Exception:
            self.quit()
            raise
        self._is_remote = False

    def __repr__(self):
        return f'<{type(self).__module__}.{type(self).__name__} (session="{self.target_id}")>'

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
        from pycdp.asyncio import connect_cdp
        from pycdp import cdp

        if self._loop:
            self._switch_to = SyncSwitchTo(driver=self, loop=self._loop)

        options = capabilities["goog:chromeOptions"]

        browser = subprocess.Popen(
            [options["binary"], *options["args"]],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=IS_POSIX,
        )

        if self._options.debugger_address.split(":")[1] == "0":
            path = self._options.user_data_dir + "/DevToolsActivePort"
            while not os.path.isfile(path):
                await self.implicitly_wait(0.1)
            self._options.debugger_address = "localhost:" + read(path, sel_root=False).split("\n")[0]
        self._conn = await connect_cdp(f'http://{self._options.debugger_address}')
        self.browser_pid = browser.pid
        targets = await self._conn.execute(cdp.target.get_targets())
        for target in targets:
            if target.type_ == "page":
                self.target_id = target.target_id
                break
        self.session = await self._conn.connect_session(self.target_id)
        self.caps = capabilities

    async def create_web_element(self, element_id: str) -> WebElement:
        """Creates a web element with the specified `element_id`."""
        raise NotImplementedError()

    async def execute(self, driver_command: str = None, params: dict = None, cmd=None):
        """
        executes on current pycdp.cdp cmd on current session
        driver_command and params aren't used
        """
        if driver_command or params:
            raise NotImplementedError("chrome not started with chromedriver")
        return await self.session.execute(cmd=cmd)

    async def get(self, url: str) -> None:
        """Loads a web page in the current browser session."""
        from pycdp import cdp
        await self.execute(cmd=cdp.page.enable())

        async def get(_url: str):
            with self.session.safe_wait_for(cdp.page.DomContentEventFired) as navigation:
                await self.session.execute(cmd=cdp.page.navigate(_url))
                await navigation

        try:
            await asyncio.wait_for(get(url), self._page_load_timeout)
        except asyncio.exceptions.TimeoutError:
            raise TimeoutError(f"page didn't load within timeout of {self._page_load_timeout}")

    @property
    async def title(self) -> str:
        """Returns the title of the current page.

        :Usage:
            ::

                title = driver.title
        """
        target = await self.current_target
        return target.title

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

    async def execute_script(self, script, *args):
        """Synchronously Executes JavaScript in the current window/frame.

        :Args:
         - script: The JavaScript to execute.
         - \\*args: Any applicable arguments for your JavaScript.

        :Usage:
            ::

                driver.execute_script('return document.title;')
        """
        import json
        from pycdp import cdp
        if isinstance(script, ScriptKey):
            try:
                script = self.pinned_scripts[script.id]
            except KeyError:
                raise JavascriptException("Pinned script could not be found")

        script = f"(function(...arguments){{{script}}})(...{json.dumps(args)})"

        script = cdp.runtime.evaluate(expression=script, include_command_line_api=True,
                                      user_gesture=True, await_promise=False,
                                      allow_unsafe_eval_blocked_by_csp=True, return_by_value=True)
        result = await asyncio.wait_for(self.execute(cmd=script), self._script_timeout)
        if result[1]:
            class JSEvalException(result[1], Exception):
                pass

            raise JSEvalException(result[1].description)
        return result[0].value

    async def execute_async_script(self, script: str, *args):
        """Asynchronously Executes JavaScript in the current window/frame.

        :Args:
         - script: The JavaScript to execute.
         - \\*args: Any applicable arguments for your JavaScript.

        :Usage:
            ::

                script = "var callback = arguments[arguments.length - 1]; " \\
                         "window.setTimeout(function(){ callback('timeout') }, 3000);"
                driver.execute_async_script(script)
        """
        from pycdp import cdp
        import json
        script = """
        (function(...arguments){
            const promise = new Promise((resolve, reject) => {
                arguments.push(resolve)
            });""" + script + ";return promise})(..." + json.dumps(args) + ")"
        timeout = cdp.runtime.TimeDelta
        timeout = timeout.from_json(self._script_timeout)
        script = cdp.runtime.evaluate(expression=script, include_command_line_api=True,
                                      user_gesture=True, await_promise=True,
                                      allow_unsafe_eval_blocked_by_csp=True, timeout=timeout)
        result = await asyncio.wait_for(self.execute(cmd=script), timeout=self._script_timeout)
        if result[1]:
            raise Exception(result[1].description)
        return result[0].value

    @property
    async def current_url(self) -> str:
        """Gets the URL of the current page.

        :Usage:
            ::

                driver.current_url
        """
        target = await self.current_target
        return target.url

    @property
    async def page_source(self) -> str:
        """Gets the source of the current page.

        :Usage:
            ::

                driver.page_source
        """
        return await self.execute_script("return document.documentElement.outerHTML")

    async def close(self) -> None:
        """Closes the current window.

        :Usage:
            ::

                driver.close()
        """
        from pycdp import cdp
        window_handles = await self.window_handles
        await self.execute(cmd=cdp.page.close())
        await self.switch_to.window(window_handles[0])

    async def quit(self) -> None:
        """Quits the driver and closes every associated window.

        :Usage:
            ::

                driver.quit()
        """
        import os
        import shutil
        # noinspection PyBroadException,PyUnusedLocal
        try:
            try:
                await self._conn.close()

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
    async def targets(self):
        from pycdp import cdp
        return await self.execute(cmd=cdp.target.get_targets())

    @property
    async def current_target(self):
        from pycdp import cdp
        return await self.execute(cmd=cdp.target.get_target_info(await self.current_window_handle))

    @property
    async def current_window_handle(self) -> pycdp.cdp.target.TargetID:
        """Returns the handle of the current window.

        :Usage:
            ::

                driver.current_window_handle
        """
        # noinspection PyProtectedMember
        return self.session._target_id

    @property
    async def current_window_id(self):
        from pycdp import cdp
        target_id = await self.current_window_handle
        script = cdp.browser.get_window_for_target(target_id)
        result = await self.execute(cmd=script)
        return result[0]

    @property
    async def window_handles(self) -> List[str]:
        """Returns the handles of all windows within the current session.

        :Usage:
            ::

                driver.window_handles
        """
        tabs = []
        for target in await self.targets:
            if target.type_ == "page":
                tabs.append(target.target_id)
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
        from pycdp import cdp
        options = {}
        if print_options:
            options = print_options.to_dict()
            raise NotImplementedError()

        page = await self.execute(cmd=cdp.page.print_to_pdf())
        return page[0]

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
        from pycdp import cdp
        await self.execute(cmd=cdp.page.reload())

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

    # noinspection PyUnusedLocal
    async def find_element(self, by=By.ID, value: Optional[str] = None) -> WebElement:
        """Find an element given a By strategy and locator.

        :Usage:
            ::

                element = driver.find_element(By.ID, 'foo')

        :rtype: WebElement
        """
        # by = RelativeBy({by: value})
        if isinstance(by, RelativeBy):
            elements = await self.find_elements(by=by, value=value)
            if not elements:
                raise NoSuchElementException(f"Cannot locate relative element with: {by.root}")
            return elements[0]

        if by == By.ID:
            by = By.CSS_SELECTOR
            value = f'[id="{value}"]'
        elif by == By.CLASS_NAME:
            by = By.CSS_SELECTOR
            value = f".{value}"
        elif by == By.NAME:
            by = By.CSS_SELECTOR
            value = f'[name="{value}"]'

        raise NotImplementedError("not started with chromedriver")

    # noinspection PyUnusedLocal
    async def find_elements(self, by=By.ID, value: Optional[str] = None) -> List[WebElement]:
        """Find elements given a By strategy and locator.

        :Usage:
            ::

                elements = driver.find_elements(By.CLASS_NAME, 'foo')

        :rtype: list of WebElement
        """
        from selenium_driverless.utils.utils import sel_path, read
        # by = RelativeBy({by: value})
        if isinstance(by, RelativeBy):
            _pkg = ".".join(__name__.split(".")[:-1])
            raw_function = read(sel_path() + "webdriver/remote/findElements.js", sel_root=False)
            find_element_js = f"/* findElements */return ({raw_function}).apply(null, arguments);"
            return await self.execute_script(find_element_js, by.to_dict())

        if by == By.ID:
            by = By.CSS_SELECTOR
            value = f'[id="{value}"]'
        elif by == By.CLASS_NAME:
            by = By.CSS_SELECTOR
            value = f".{value}"
        elif by == By.NAME:
            by = By.CSS_SELECTOR
            value = f'[name="{value}"]'

        # Return empty list if driver returns null
        # See https://github.com/SeleniumHQ/selenium/issues/4555
        raise NotImplementedError("not started with chromedriver")

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
        from pycdp import cdp
        return await self.execute(cmd=cdp.page.capture_screenshot(format_="png"))

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
        from pycdp import cdp
        script = cdp.browser.get_window_bounds(await self.current_window_id)
        bounds = await self.execute(cmd=script)
        json = bounds.to_json()
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
        from pycdp import cdp

        if (x is None and y is None) and (not height and not width):
            raise InvalidArgumentException("x and y or height and width need values")

        json = {"left": x, "top": y, "width": width, 'height': height}
        bounds = cdp.browser.Bounds()
        bounds = bounds.from_json(json=json)

        script = cdp.browser.set_window_bounds(await self.current_window_id, bounds)
        await self.execute(cmd=script)
        json["x"] = json["left"]
        del json["left"]
        json["y"] = json["top"]
        del json["top"]

        return json

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

    async def set_network_conditions(self, **network_conditions) -> None:
        """Sets Chromium network emulation settings.

        :Args:
         - network_conditions: A dict with conditions specification.

        :Usage:
            ::

                driver.set_network_conditions(
                    offline=False,
                    latency=5,  # additional latency (ms)
                    download_throughput=500 * 1024,  # maximal throughput
                    upload_throughput=500 * 1024)  # maximal throughput

            Note: 'throughput' can be used to set both (for download and upload).
        """
        from pycdp import cdp
        await self.execute(cmd=cdp.network.emulate_network_conditions(**network_conditions))

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

    async def execute_cdp_cmd(self, cmd: str, cmd_args: dict or None = None):
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
        if not cmd_args:
            cmd_args = {}

        def execute_cdp_cmd(_cmd_dict):
            json = yield _cmd_dict
            return json

        cmd_dict = dict(method=cmd, params=cmd_args)
        request = execute_cdp_cmd(cmd_dict)
        return await self.execute(cmd=request)

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
