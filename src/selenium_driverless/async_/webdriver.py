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
import contextlib
import copy
import os.path
import pkgutil
import subprocess
import types
import typing
import warnings
from abc import ABCMeta
from base64 import b64decode
from base64 import urlsafe_b64encode
from contextlib import asynccontextmanager
from importlib import import_module
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from selenium.common.exceptions import InvalidArgumentException
from selenium.common.exceptions import JavascriptException
from selenium.common.exceptions import NoSuchCookieException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.html5.application_cache import ApplicationCache
from selenium_driverless.scripts.options import Options as BaseOptions
from selenium.webdriver.common.print_page_options import PrintOptions
from selenium.webdriver.common.timeouts import Timeouts
from selenium.webdriver.common.virtual_authenticator import Credential
from selenium.webdriver.common.virtual_authenticator import VirtualAuthenticatorOptions
from selenium.webdriver.common.virtual_authenticator import (
    required_virtual_authenticator,
)
from selenium.webdriver.remote.bidi_connection import BidiConnection
from selenium.webdriver.remote.command import Command
from selenium.webdriver.remote.errorhandler import ErrorHandler
from selenium.webdriver.remote.file_detector import FileDetector
from selenium.webdriver.remote.file_detector import LocalFileDetector
from selenium_driverless.async_.mobile import Mobile
from selenium.webdriver.remote.script_key import ScriptKey
from selenium.webdriver.remote.shadowroot import ShadowRoot
from selenium.webdriver.remote.switch_to import SwitchTo
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.relative_locator import RelativeBy
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium_driverless.scripts.options import Options

cdp = None


def import_cdp():
    global cdp
    if not cdp:
        cdp = import_module("selenium.webdriver.common.bidi.cdp")


def _create_caps(caps):
    """Makes a W3C alwaysMatch capabilities object.

    Filters out capability names that are not in the W3C spec. Spec-compliant
    drivers will reject requests containing unknown capability names.

    Moves the Firefox profile, if present, from the old location to the new Firefox
    options object.

    :Args:
     - caps - A dictionary of capabilities requested by the caller.
    """
    caps = copy.deepcopy(caps)
    always_match = {}
    for k, v in caps.items():
        always_match[k] = v
    return {"capabilities": {"firstMatch": [{}], "alwaysMatch": always_match}}


def create_matches(options: List[BaseOptions]) -> Dict:
    capabilities = {"capabilities": {}}
    opts = []
    for opt in options:
        opts.append(opt.to_capabilities())
    opts_size = len(opts)
    samesies = {}

    # Can not use bitwise operations on the dicts or lists due to
    # https://bugs.python.org/issue38210
    for i in range(opts_size):
        min_index = i
        if i + 1 < opts_size:
            first_keys = opts[min_index].keys()

            for kys in first_keys:
                if kys in opts[i + 1].keys():
                    if opts[min_index][kys] == opts[i + 1][kys]:
                        samesies.update({kys: opts[min_index][kys]})

    always = {}
    for k, v in samesies.items():
        always[k] = v

    for i in opts:
        for k in always:
            del i[k]

    capabilities["capabilities"]["alwaysMatch"] = always
    capabilities["capabilities"]["firstMatch"] = opts

    return capabilities


class BaseWebDriver(metaclass=ABCMeta):
    """Abstract Base Class for all Webdriver subtypes.

    ABC's allow custom implementations of Webdriver to be registered so
    that isinstance type checks will succeed.
    """


class ChromeDriver(BaseWebDriver):
    """Allows you to drive the browser without chromedriver."""

    _web_element_cls = WebElement
    _shadowroot_cls = ShadowRoot

    def __init__(
            self,
            options: Options = None
    ) -> None:
        """Creates a new instance of the chrome driver. Starts the service and
        then creates new instance of chrome driver.

        :Args:
         - options - this takes an instance of ChromeOptions
        """
        self.session = None
        self.conn = None
        self.browser_pid = None
        async_used = None
        try:
            self._loop = asyncio.get_running_loop()
            async_used = True
        except RuntimeError:
            self._loop = asyncio.get_event_loop()

        try:
            options = options or Options()
            self._options = options

            browser_name = DesiredCapabilities.CHROME["browserName"],
            vendor_prefix = "goog"
            self.vendor_prefix = vendor_prefix

            if isinstance(options, list):
                self._capabilities = create_matches(options)
            else:
                self._capabilities = options.to_capabilities()
            self._is_remote = True
            self.session_id = None
            self.caps = {}
            self.pinned_scripts = {}
            self.error_handler = ErrorHandler()
            self._switch_to = SwitchTo(self)
            self._mobile = Mobile(self)
            self.file_detector = LocalFileDetector()
            self._authenticator_id = None
            self.start_client()
            if not async_used:
                self._loop.run_until_complete(self.start_session(self._capabilities))

        except Exception:
            self.quit()
            raise
        self._is_remote = False

    def __repr__(self):
        return f'<{type(self).__module__}.{type(self).__name__} (session="{self.session_id}")>'

    def __enter__(self):
        return self

    def __exit__(
            self,
            exc_type: typing.Optional[typing.Type[BaseException]],
            exc: typing.Optional[BaseException],
            traceback: typing.Optional[types.TracebackType],
    ):
        self.quit()

    @property
    def mobile(self) -> Mobile:
        return self._mobile

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

    def start_client(self):
        """Called before starting a new session.

        This method may be overridden to define custom startup behavior.
        """
        pass

    def stop_client(self):
        """Called after executing a quit command.

        This method may be overridden to define custom shutdown
        behavior.
        """
        pass

    async def start_session(self, capabilities: dict or None = None) -> None:
        """Creates a new session with the desired capabilities.

        :Args:
         - capabilities - a capabilities dict to start the session with.
        """
        if not capabilities:
            capabilities = self._capabilities
        del self._capabilities
        from selenium_driverless.utils.utils import IS_POSIX, read
        from pycdp.asyncio import connect_cdp
        from pycdp import cdp

        options = capabilities["goog:chromeOptions"]
        caps = _create_caps(capabilities)

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
                await asyncio.sleep(0.1)
            self._options.debugger_address = "localhost:" + read(path, sel_root=False).split("\n")[0]
        self.conn = await connect_cdp(f'http://{self._options.debugger_address}')
        self.browser_pid = browser.pid
        targets = await self.conn.execute(cdp.target.get_targets())
        for target in targets:
            if target.type_ == "page":
                self.session_id = target.target_id
                break
        self.session = await self.conn.connect_session(self.session_id)
        self.caps = capabilities

    def _wrap_value(self, value):
        if isinstance(value, dict):
            converted = {}
            for key, val in value.items():
                converted[key] = self._wrap_value(val)
            return converted
        if isinstance(value, self._web_element_cls):
            return {"element-6066-11e4-a52e-4f735466cecf": value.id}
        if isinstance(value, self._shadowroot_cls):
            return {"shadow-6066-11e4-a52e-4f735466cecf": value.id}
        if isinstance(value, list):
            return list(self._wrap_value(item) for item in value)
        return value

    def create_web_element(self, element_id: str) -> WebElement:
        """Creates a web element with the specified `element_id`."""
        return self._web_element_cls(self, element_id)

    def _unwrap_value(self, value):
        if isinstance(value, dict):
            if "element-6066-11e4-a52e-4f735466cecf" in value:
                return self.create_web_element(value["element-6066-11e4-a52e-4f735466cecf"])
            if "shadow-6066-11e4-a52e-4f735466cecf" in value:
                return self._shadowroot_cls(self, value["shadow-6066-11e4-a52e-4f735466cecf"])
            for key, val in value.items():
                value[key] = self._unwrap_value(val)
            return value
        if isinstance(value, list):
            return list(self._unwrap_value(item) for item in value)
        return value

    async def execute(self, driver_command: str, params: dict = None) -> dict:
        """Sends a command to be executed by a command.CommandExecutor.

        :Args:
         - driver_command: The name of the command to execute as a string.
         - params: A dictionary of named parameters to send with the command.

        :Returns:
          The command's JSON response loaded into a dictionary object.
        """
        if driver_command == "executeCdpCommand":
            value = await self.execute_cdp_cmd(params["script"], params["params"])
            return {"success": 0, "value": value, "sessionId": self.session_id}
        else:
            raise NotImplementedError("chrome not started with chromedriver")

    async def get(self, url: str) -> None:
        from pycdp import cdp
        """Loads a web page in the current browser session."""
        await self.session.execute(cdp.page.enable())
        with self.session.safe_wait_for(cdp.page.DomContentEventFired) as navigation:
            await self.session.execute(cdp.page.navigate(url))
            await navigation

    @property
    def title(self) -> str:
        """Returns the title of the current page.

        :Usage:
            ::

                title = driver.title
        """
        return self.execute(Command.GET_TITLE).get("value", "")

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

    def execute_script(self, script, *args):
        """Synchronously Executes JavaScript in the current window/frame.

        :Args:
         - script: The JavaScript to execute.
         - \\*args: Any applicable arguments for your JavaScript.

        :Usage:
            ::

                driver.execute_script('return document.title;')
        """
        if isinstance(script, ScriptKey):
            try:
                script = self.pinned_scripts[script.id]
            except KeyError:
                raise JavascriptException("Pinned script could not be found")

        converted_args = list(args)
        command = Command.W3C_EXECUTE_SCRIPT

        return self.execute(command, {"script": script, "args": converted_args})["value"]

    def execute_async_script(self, script: str, *args):
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
        converted_args = list(args)
        command = Command.W3C_EXECUTE_SCRIPT_ASYNC

        return self.execute(command, {"script": script, "args": converted_args})["value"]

    @property
    def current_url(self) -> str:
        """Gets the URL of the current page.

        :Usage:
            ::

                driver.current_url
        """
        return self.execute(Command.GET_CURRENT_URL)["value"]

    @property
    def page_source(self) -> str:
        """Gets the source of the current page.

        :Usage:
            ::

                driver.page_source
        """
        return self.execute(Command.GET_PAGE_SOURCE)["value"]

    def close(self) -> None:
        """Closes the current window.

        :Usage:
            ::

                driver.close()
        """
        self.execute(Command.CLOSE)

    async def quit(self) -> None:
        """Quits the driver and closes every associated window.

        :Usage:
            ::

                driver.quit()
        """
        import os
        import shutil
        import time
        from pycdp import cdp
        # noinspection PyBroadException
        try:
            try:
                await self.session.execute(cdp.page.close())
                # wait for process to be killed
                while True:
                    try:
                        os.kill(self.browser_pid, 15)
                    except OSError:
                        break
                    time.sleep(0.1)

                shutil.rmtree(self._options.user_data_dir, ignore_errors=True)
            finally:
                self.stop_client()
        except Exception:
            # We don't care about the message because something probably has gone wrong
            pass
        finally:
            pass  # self.service.stop()

    @property
    def current_window_handle(self) -> str:
        """Returns the handle of the current window.

        :Usage:
            ::

                driver.current_window_handle
        """
        return self.execute(Command.W3C_GET_CURRENT_WINDOW_HANDLE)["value"]

    @property
    def window_handles(self) -> List[str]:
        """Returns the handles of all windows within the current session.

        :Usage:
            ::

                driver.window_handles
        """
        return self.execute(Command.W3C_GET_WINDOW_HANDLES)["value"]

    def maximize_window(self) -> None:
        """Maximizes the current window that webdriver is using."""
        command = Command.W3C_MAXIMIZE_WINDOW
        self.execute(command, None)

    def fullscreen_window(self) -> None:
        """Invokes the window manager-specific 'full screen' operation."""
        self.execute(Command.FULLSCREEN_WINDOW)

    def minimize_window(self) -> None:
        """Invokes the window manager-specific 'minimize' operation."""
        self.execute(Command.MINIMIZE_WINDOW)

    def print_page(self, print_options: Optional[PrintOptions] = None) -> str:
        """Takes PDF of the current page.

        The driver makes a best effort to return a PDF based on the
        provided parameters.
        """
        options = {}
        if print_options:
            options = print_options.to_dict()

        return self.execute(Command.PRINT_PAGE, options)["value"]

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

    # Navigation
    def back(self) -> None:
        """Goes one step backward in the browser history.

        :Usage:
            ::

                driver.back()
        """
        self.execute(Command.GO_BACK)

    def forward(self) -> None:
        """Goes one step forward in the browser history.

        :Usage:
            ::

                driver.forward()
        """
        self.execute(Command.GO_FORWARD)

    def refresh(self) -> None:
        """Refreshes the current page.

        :Usage:
            ::

                driver.refresh()
        """
        self.execute(Command.REFRESH)

    # Options
    def get_cookies(self) -> List[dict]:
        """Returns a set of dictionaries, corresponding to cookies visible in
        the current session.

        :Usage:
            ::

                driver.get_cookies()
        """
        return self.execute(Command.GET_ALL_COOKIES)["value"]

    def get_cookie(self, name) -> typing.Optional[typing.Dict]:
        """Get a single cookie by name. Returns the cookie if found, None if
        not.

        :Usage:
            ::

                driver.get_cookie('my_cookie')
        """
        with contextlib.suppress(NoSuchCookieException):
            return self.execute(Command.GET_COOKIE, {"name": name})["value"]
        return None

    def delete_cookie(self, name) -> None:
        """Deletes a single cookie with the given name.

        :Usage:
            ::

                driver.delete_cookie('my_cookie')
        """
        self.execute(Command.DELETE_COOKIE, {"name": name})

    def delete_all_cookies(self) -> None:
        """Delete all cookies in the scope of the session.

        :Usage:
            ::

                driver.delete_all_cookies()
        """
        self.execute(Command.DELETE_ALL_COOKIES)

    def add_cookie(self, cookie_dict) -> None:
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
            self.execute(Command.ADD_COOKIE, {"cookie": cookie_dict})
        else:
            self.execute(Command.ADD_COOKIE, {"cookie": cookie_dict})

    # Timeouts
    def implicitly_wait(self, time_to_wait: float) -> None:
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
        self.execute(Command.SET_TIMEOUTS, {"implicit": int(float(time_to_wait) * 1000)})

    def set_script_timeout(self, time_to_wait: float) -> None:
        """Set the amount of time that the script should wait during an
        execute_async_script call before throwing an error.

        :Args:
         - time_to_wait: The amount of time to wait (in seconds)

        :Usage:
            ::

                driver.set_script_timeout(30)
        """
        self.execute(Command.SET_TIMEOUTS, {"script": int(float(time_to_wait) * 1000)})

    def set_page_load_timeout(self, time_to_wait: float) -> None:
        """Set the amount of time to wait for a page load to complete before
        throwing an error.

        :Args:
         - time_to_wait: The amount of time to wait

        :Usage:
            ::

                driver.set_page_load_timeout(30)
        """
        try:
            self.execute(Command.SET_TIMEOUTS, {"pageLoad": int(float(time_to_wait) * 1000)})
        except WebDriverException:
            self.execute(Command.SET_TIMEOUTS, {"ms": float(time_to_wait) * 1000, "type": "page load"})

    @property
    def timeouts(self) -> Timeouts:
        """Get all the timeouts that have been set on the current session.

        :Usage:
            ::

                driver.timeouts
        :rtype: Timeout
        """
        timeouts = self.execute(Command.GET_TIMEOUTS)["value"]
        timeouts["implicit_wait"] = timeouts.pop("implicit") / 1000
        timeouts["page_load"] = timeouts.pop("pageLoad") / 1000
        timeouts["script"] = timeouts.pop("script") / 1000
        return Timeouts(**timeouts)

    @timeouts.setter
    def timeouts(self, timeouts) -> None:
        # noinspection GrazieInspection
        """Set all timeouts for the session. This will override any previously
                set timeouts.

                :Usage:
                    ::
                        my_timeouts = Timeouts()
                        my_timeouts.implicit_wait = 10
                        driver.timeouts = my_timeouts
                """
        _ = self.execute(Command.SET_TIMEOUTS, timeouts._to_json())["value"]

    def find_element(self, by=By.ID, value: Optional[str] = None) -> WebElement:
        """Find an element given a By strategy and locator.

        :Usage:
            ::

                element = driver.find_element(By.ID, 'foo')

        :rtype: WebElement
        """
        if isinstance(by, RelativeBy):
            elements = self.find_elements(by=by, value=value)
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

        return self.execute(Command.FIND_ELEMENT, {"using": by, "value": value})["value"]

    def find_elements(self, by=By.ID, value: Optional[str] = None) -> List[WebElement]:
        """Find elements given a By strategy and locator.

        :Usage:
            ::

                elements = driver.find_elements(By.CLASS_NAME, 'foo')

        :rtype: list of WebElement
        """
        if isinstance(by, RelativeBy):
            _pkg = ".".join(__name__.split(".")[:-1])
            raw_function = pkgutil.get_data(_pkg, "findElements.js").decode("utf8")
            find_element_js = f"/* findElements */return ({raw_function}).apply(null, arguments);"
            return self.execute_script(find_element_js, by.to_dict())

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
        return self.execute(Command.FIND_ELEMENTS, {"using": by, "value": value})["value"] or []

    @property
    def desired_capabilities(self) -> dict:
        """returns the drivers current desired capabilities being used."""
        warnings.warn("desired_capabilities is deprecated. Please call capabilities.", DeprecationWarning, stacklevel=2)
        return self.caps

    @property
    def capabilities(self) -> dict:
        """returns the drivers current capabilities being used."""
        return self.caps

    def get_screenshot_as_file(self, filename) -> bool:
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
        png = self.get_screenshot_as_png()
        try:
            with open(filename, "wb") as f:
                f.write(png)
        except OSError:
            return False
        finally:
            del png
        return True

    def save_screenshot(self, filename) -> bool:
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
        return self.get_screenshot_as_file(filename)

    def get_screenshot_as_png(self) -> bytes:
        """Gets the screenshot of the current window as a binary data.

        :Usage:
            ::

                driver.get_screenshot_as_png()
        """
        return b64decode(self.get_screenshot_as_base64().encode("ascii"))

    def get_screenshot_as_base64(self) -> str:
        """Gets the screenshot of the current window as a base64 encoded string
        which is useful in embedded images in HTML.

        :Usage:
            ::

                driver.get_screenshot_as_base64()
        """
        return self.execute(Command.SCREENSHOT)["value"]

    # noinspection PyPep8Naming
    def set_window_size(self, width, height, windowHandle: str = "current") -> None:
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
        self.set_window_rect(width=int(width), height=int(height))

    # noinspection PyPep8Naming
    def get_window_size(self, windowHandle: str = "current") -> dict:
        """Gets the width and height of the current window.

        :Usage:
            ::

                driver.get_window_size()
        """

        if windowHandle != "current":
            warnings.warn("Only 'current' window is supported for W3C compatible browsers.")
        size = self.get_window_rect()

        if size.get("value", None):
            size = size["value"]

        return {k: size[k] for k in ("width", "height")}

    # noinspection PyPep8Naming
    def set_window_position(self, x, y, windowHandle: str = "current") -> dict:
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
        return self.set_window_rect(x=int(x), y=int(y))

    # noinspection PyPep8Naming
    def get_window_position(self, windowHandle="current") -> dict:
        """Gets the x,y position of the current window.

        :Usage:
            ::

                driver.get_window_position()
        """

        if windowHandle != "current":
            warnings.warn("Only 'current' window is supported for W3C compatible browsers.")
        position = self.get_window_rect()

        return {k: position[k] for k in ("x", "y")}

    def get_window_rect(self) -> dict:
        """Gets the x, y coordinates of the window as well as height and width
        of the current window.

        :Usage:
            ::

                driver.get_window_rect()
        """
        return self.execute(Command.GET_WINDOW_RECT)["value"]

    def set_window_rect(self, x=None, y=None, width=None, height=None) -> dict:
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

        return self.execute(Command.SET_WINDOW_RECT, {"x": x, "y": y, "width": width, "height": height})["value"]

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
        return self.execute(Command.GET_SCREEN_ORIENTATION)["value"]

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
            self.execute(Command.SET_SCREEN_ORIENTATION, {"orientation": value})
        else:
            raise WebDriverException("You can only set the orientation to 'LANDSCAPE' and 'PORTRAIT'")

    @property
    def application_cache(self):
        """Returns a ApplicationCache Object to interact with the browser app
        cache."""
        return ApplicationCache(self)

    @property
    def log_types(self):
        """Gets a list of the available log types. This only works with w3c
        compliant browsers.

        :Usage:
            ::

                driver.log_types
        """
        return self.execute(Command.GET_AVAILABLE_LOG_TYPES)["value"]

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
        return self.execute(Command.GET_LOG, {"type": log_type})["value"]

    @asynccontextmanager
    async def bidi_connection(self):
        global cdp
        import_cdp()
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
        _firefox = False
        if self.caps.get("browserName") == "chrome":
            debugger_address = self.caps.get("goog:chromeOptions").get("debuggerAddress")
        elif self.caps.get("browserName") == "msedge":
            debugger_address = self.caps.get("ms:edgeOptions").get("debuggerAddress")
        else:
            _firefox = True
            debugger_address = self.caps.get("moz:debuggerAddress")
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
        self._authenticator_id = self.execute(Command.ADD_VIRTUAL_AUTHENTICATOR, options.to_dict())["value"]

    @property
    def virtual_authenticator_id(self) -> str:
        """Returns the id of the virtual authenticator."""
        return self._authenticator_id

    @required_virtual_authenticator
    def remove_virtual_authenticator(self) -> None:
        """Removes a previously added virtual authenticator.

        The authenticator is no longer valid after removal, so no
        methods may be called.
        """
        self.execute(Command.REMOVE_VIRTUAL_AUTHENTICATOR, {"authenticatorId": self._authenticator_id})
        self._authenticator_id = None

    @required_virtual_authenticator
    def add_credential(self, credential: Credential) -> None:
        """Injects a credential into the authenticator."""
        self.execute(Command.ADD_CREDENTIAL, {**credential.to_dict(), "authenticatorId": self._authenticator_id})

    @required_virtual_authenticator
    def get_credentials(self) -> List[Credential]:
        """Returns the list of credentials owned by the authenticator."""
        credential_data = self.execute(Command.GET_CREDENTIALS, {"authenticatorId": self._authenticator_id})
        return [Credential.from_dict(credential) for credential in credential_data["value"]]

    @required_virtual_authenticator
    def remove_credential(self, credential_id: Union[str, bytearray]) -> None:
        """Removes a credential from the authenticator."""
        # Check if the credential is bytearray converted to b64 string
        if isinstance(credential_id, bytearray):
            credential_id = urlsafe_b64encode(credential_id).decode()

        self.execute(
            Command.REMOVE_CREDENTIAL, {"credentialId": credential_id, "authenticatorId": self._authenticator_id}
        )

    @required_virtual_authenticator
    def remove_all_credentials(self) -> None:
        """Removes all credentials from the authenticator."""
        self.execute(Command.REMOVE_ALL_CREDENTIALS, {"authenticatorId": self._authenticator_id})

    @required_virtual_authenticator
    def set_user_verified(self, verified: bool) -> None:
        """Sets whether the authenticator will simulate success or fail on user
        verification.

        verified: True if the authenticator will pass user verification, False otherwise.
        """
        self.execute(Command.SET_USER_VERIFIED, {"authenticatorId": self._authenticator_id, "isUserVerified": verified})

    #
    # selenium.webdriver.chrome.WebDriver props from here on
    #

    def launch_app(self, id):
        """Launches Chromium app specified by id."""
        return self.execute("launchApp", {"id": id})

    def get_network_conditions(self):
        """Gets Chromium network emulation settings.

        :Returns:
            A dict. For example:
            {'latency': 4, 'download_throughput': 2, 'upload_throughput': 2,
            'offline': False}
        """
        return self.execute("getNetworkConditions")["value"]

    def set_network_conditions(self, **network_conditions) -> None:
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
        self.execute("setNetworkConditions", {"network_conditions": network_conditions})

    def delete_network_conditions(self) -> None:
        """Resets Chromium network emulation settings."""
        self.execute("deleteNetworkConditions")

    def set_permissions(self, name: str, value: str) -> None:
        """Sets Applicable Permission.

        :Args:
         - name: The item to set the permission on.
         - value: The value to set on the item

        :Usage:
            ::

                driver.set_permissions('clipboard-read', 'denied')
        """
        self.execute("setPermissions", {"descriptor": {"name": name}, "state": value})

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

        def execute_cdp_cmd(cmd_dict):
            json = yield cmd_dict
            return json

        cmd_dict = dict(method=cmd, params=cmd_args)
        request = execute_cdp_cmd(cmd_dict)
        return await self.conn.execute(request)

    def get_sinks(self) -> list:
        """
        :Returns: A list of sinks available for Cast.
        """
        return self.execute("getSinks")["value"]

    def get_issue_message(self):
        """
        :Returns: An error message when there is any issue in a Cast session.
        """
        return self.execute("getIssueMessage")["value"]

    def set_sink_to_use(self, sink_name: str) -> dict:
        """Sets a specific sink, using its name, as a Cast session receiver
        target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        return self.execute("setSinkToUse", {"sinkName": sink_name})

    def start_desktop_mirroring(self, sink_name: str) -> dict:
        """Starts a desktop mirroring session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        return self.execute("startDesktopMirroring", {"sinkName": sink_name})

    def start_tab_mirroring(self, sink_name: str) -> dict:
        """Starts a tab mirroring session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to use as the target.
        """
        return self.execute("startTabMirroring", {"sinkName": sink_name})

    def stop_casting(self, sink_name: str) -> dict:
        """Stops the existing Cast session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to stop the Cast session.
        """
        return self.execute("stopCasting", {"sinkName": sink_name})
