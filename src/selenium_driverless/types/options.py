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

import base64
import os
import warnings
from abc import ABCMeta
from typing import Union, Optional, List, BinaryIO

# selenium
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.proxy import Proxy


# noinspection PyUnreachableCode,PyUnusedLocal
class Options(metaclass=ABCMeta):
    KEY = "goog:chromeOptions"

    def __init__(self) -> None:
        from selenium_driverless.utils.utils import find_chrome_executable, IS_POSIX
        super().__init__()

        self._caps = self.default_capabilities
        self._proxy = None
        # self.set_capability("pageLoadStrategy", "normal")
        self.mobile_options = None

        self._binary_location = find_chrome_executable()
        self._extension_files = []
        self._extensions = []
        self._experimental_options = {}
        self._debugger_address = None
        self.user_data_dir = None
        self._arguments = []
        self._ignore_local_proxy = False

        self.add_argument("--no-first-run")
        self.add_argument('--disable-component-update')
        self.add_argument('--no-service-autorun')
        if IS_POSIX:
            self.add_argument("--password-store=basic")

        # to support multiple instances
        self.add_argument('--disable-backgrounding-occluded-windows')
        self.add_argument('--disable-renderer-backgrounding')

        self.add_argument('--disable-background-timer-throttling')
        self.add_argument('--disable-renderer-backgrounding')
        self.add_argument('--disable-background-networking')
        self.add_argument('--no-pings')

        self.add_argument('--disable-infobars')
        self.add_argument('--disable-breakpad')
        self.add_argument("--no-default-browser-check")
        self.add_argument('--homepage=about:blank')

        self._is_remote = True

    @property
    def capabilities(self):
        return self._caps

    def set_capability(self, name: str, value: dict) -> None:
        """Sets a capability."""
        if name == "proxy":
            proxy = None
            proxy_keys = ['ftpProxy', 'httpProxy', 'sslProxy']
            warnings.warn("not started with chromedriver, only aplying single proxy")
            for key, value in value.items():
                if key in proxy_keys:
                    self.add_argument(f'--proxy-server={value}')
                    if not proxy:
                        proxy = value
                    value[key] = proxy
            self._proxy = Proxy(value)
        else:
            raise NotImplementedError()
        self._caps[name] = value

    @property
    def browser_version(self) -> str:
        """
        :returns: the version of the browser if set, otherwise None.
        """
        raise NotImplementedError()
        return self._caps.get("browserVersion")

    @browser_version.setter
    def browser_version(self, version: str) -> None:
        """Requires the major version of the browser to match provided value:
        https://w3c.github.io/webdriver/#dfn-browser-version.

        :param version: The required version of the browser
        """
        raise NotImplementedError()
        self.set_capability("browserVersion", version)

    @property
    def platform_name(self) -> str:
        """
        :returns: The name of the platform
        """
        raise NotImplementedError()
        return self._caps["platformName"]

    @platform_name.setter
    def platform_name(self, platform: str) -> None:
        """Requires the platform to match the provided value:
        https://w3c.github.io/webdriver/#dfn-platform-name.

        :param platform: the required name of the platform
        """
        raise NotImplementedError()
        self.set_capability("platformName", platform)

    @property
    def page_load_strategy(self) -> str:
        """
        :returns: page load strategy if set, the default is "normal"
        """
        raise NotImplementedError()
        return self._caps["pageLoadStrategy"]

    @page_load_strategy.setter
    def page_load_strategy(self, strategy: str) -> None:
        """Determines the point at which a navigation command is returned:
        https://w3c.github.io/webdriver/#dfn-table-of-page-load-strategies.

        :param strategy: the strategy corresponding to a document readiness state
        """
        raise NotImplementedError()
        if strategy in ["normal", "eager", "none"]:
            self.set_capability("pageLoadStrategy", strategy)
        else:
            raise ValueError("Strategy can only be one of the following: normal, eager, none")

    @property
    def unhandled_prompt_behavior(self) -> str:
        """
        :returns: unhandled prompt behavior if set, the default is "dismiss and notify"
        """
        raise NotImplementedError()
        return self._caps["unhandledPromptBehavior"]

    @unhandled_prompt_behavior.setter
    def unhandled_prompt_behavior(self, behavior: str) -> None:
        """How the target should respond when an alert is present and the
        command sent is not handling the alert:
        https://w3c.github.io/webdriver/#dfn-table-of-page-load-strategies.

        :param behavior: behavior to use when an alert is encountered
        """
        raise NotImplementedError()
        if behavior in ["dismiss", "accept", "dismiss and notify", "accept and notify", "ignore"]:
            self.set_capability("unhandledPromptBehavior", behavior)
        else:
            raise ValueError(
                "Behavior can only be one of the following: dismiss, accept, dismiss and notify, "
                "accept and notify, ignore"
            )

    @property
    def timeouts(self) -> dict:
        """
        :returns: Values for implicit timeout, pageLoad timeout and script timeout if set (in milliseconds)
        """
        raise NotImplementedError()
        return self._caps["timeouts"]

    @timeouts.setter
    def timeouts(self, timeouts: dict) -> None:
        """How long the target should wait for actions to complete before
        returning an error https://w3c.github.io/webdriver/#timeouts.

        :param timeouts: values in milliseconds for implicit wait, page load and script timeout
        """
        raise NotImplementedError()
        if all(x in ("implicit", "pageLoad", "script") for x in timeouts.keys()):
            self.set_capability("timeouts", timeouts)
        else:
            raise ValueError("Timeout keys can only be one of the following: implicit, pageLoad, script")

    def enable_mobile(
            self,
            android_package: str = "com.android.chrome",
            android_activity: Optional[str] = None,
            device_serial: Optional[str] = None,
    ) -> None:
        """Enables mobile browser use for browsers that support it.

        :Args:
            android_activity: The name of the android package to start
        """
        raise NotImplementedError()
        if not android_package:
            raise AttributeError("android_package must be passed in")
        self.mobile_options = {"androidPackage": android_package}
        if android_activity:
            self.mobile_options["androidActivity"] = android_activity
        if device_serial:
            self.mobile_options["androidDeviceSerial"] = device_serial

    @property
    def accept_insecure_certs(self) -> bool:
        """
        :returns: whether the session accepts insecure certificates
        """
        raise NotImplementedError()
        return self._caps.get("acceptInsecureCerts", False)

    @accept_insecure_certs.setter
    def accept_insecure_certs(self, value: bool) -> None:
        """Whether untrusted and self-signed TLS certificates are implicitly
        trusted: https://w3c.github.io/webdriver/#dfn-insecure-tls-
        certificates.

        :param value: whether to accept insecure certificates
        """
        raise NotImplementedError()
        self._caps["acceptInsecureCerts"] = value

    @property
    def strict_file_interactability(self) -> bool:
        """
        :returns: whether session is strict about file interactability
        """
        raise NotImplementedError()
        return self._caps.get("strictFileInteractability", False)

    @strict_file_interactability.setter
    def strict_file_interactability(self, value: bool) -> None:
        """Whether interactability checks will be applied to file type input
        elements. The default is false.

        :param value: whether file interactability is strict
        """
        raise NotImplementedError()
        self._caps["strictFileInteractability"] = value

    @property
    def set_window_rect(self) -> bool:
        """
        :returns: whether the remote end supports setting window size and position
        """
        return True

    @set_window_rect.setter
    def set_window_rect(self, value: bool) -> None:
        # noinspection GrazieInspection
        """Whether the remote end supports all of the resizing and positioning
                commands. The default is false. https://w3c.github.io/webdriver/#dfn-
                strict-file-interactability.

                :param value: whether remote end must support setting window resizing and repositioning
                """
        pass

    @property
    def proxy(self) -> Proxy:
        """
        :Returns: Proxy if set, otherwise None.
        """
        proxy = Proxy(self._proxy)
        return proxy

    @proxy.setter
    def proxy(self, value: Proxy) -> None:
        raise NotImplementedError()
        if not isinstance(value, Proxy):
            raise InvalidArgumentException("Only Proxy objects can be passed in.")
        warnings.warn("not started with chromedriver, only aplying single proxy")
        self.set_capability("proxy", value=value.to_dict())

    #
    # Options(BaseOptions) from here on
    #

    @property
    def arguments(self):
        """
        :Returns: A list of arguments needed for the browser
        """
        return self._arguments

    def add_argument(self, argument):
        import os
        """Adds an argument to the list.

        :Args:
         - Sets the arguments
        """
        if argument:
            if argument[:16] == "--user-data-dir=":
                user_data_dir = argument[16:]
                if not os.path.isdir(user_data_dir):
                    os.makedirs(user_data_dir, exist_ok=True)
                self.user_data_dir = user_data_dir
            elif argument[:24] == "--remote-debugging-port=":
                port = int(argument[24:])
                if not self._debugger_address:
                    self._debugger_address = f"127.0.0.1:{port}"
                self._is_remote = False
            self._arguments.append(argument)
        else:
            raise ValueError("argument can not be null")

    def ignore_local_proxy_environment_variables(self) -> None:
        """By calling this you will ignore HTTP_PROXY and HTTPS_PROXY from
        being picked up and used."""
        raise NotImplementedError()
        self._ignore_local_proxy = True

    #
    #   ChromiumOptions(ArgOptions) form here on
    #

    @property
    def binary_location(self) -> str:
        """
        :Returns: The location of the binary, otherwise an empty string
        """
        return self._binary_location

    @binary_location.setter
    def binary_location(self, value: str) -> None:
        """
        Allows you to set where the chromium binary lives
        :Args:
         - value: path to the Chromium binary
        """
        self._binary_location = value

    @property
    def debugger_address(self) -> str:
        """
        :Returns: The address of the remote devtools instance
        """
        return self._debugger_address

    @debugger_address.setter
    def debugger_address(self, value: str) -> None:
        """
        Allows you to set the address of the remote devtools instance
        that the Chrome instance will try to connect to during an
        active wait.
        :Args:
         - value: address of remote devtools instance if any (hostname[:port])
        """
        self._debugger_address = value

    @property
    def extensions(self) -> List[str]:
        """
        :Returns: A list of encoded extensions that will be loaded
        """
        raise NotImplementedError()

        def _decode(file_data: BinaryIO) -> str:
            # Should not use base64.encodestring() which inserts newlines every
            # 76 characters (per RFC 1521).  Chromedriver has to remove those
            # unnecessary newlines before decoding, causing performance hit.
            return base64.b64encode(file_data.read()).decode("utf-8")

        encoded_extensions = []
        for extension in self._extension_files:
            with open(extension, "rb") as f:
                encoded_extensions.append(_decode(f))

        return encoded_extensions + self._extensions

    def add_extension(self, extension: str) -> None:
        """Adds the path to the extension to a list that will be used to
        extract it to the Chrome.

        :Args:
         - extension: path to the \\*.crx file
        """
        raise NotImplementedError()
        if extension:
            extension_to_add = os.path.abspath(os.path.expanduser(extension))
            if os.path.exists(extension_to_add):
                self._extension_files.append(extension_to_add)
            else:
                raise OSError("Path to the extension doesn't exist")
        else:
            raise ValueError("argument can not be null")

    def add_encoded_extension(self, extension: str) -> None:
        """Adds Base64 encoded string with extension data to a list that will
        be used to extract it to the Chrome.

        :Args:
         - extension: Base64 encoded string with extension data
        """
        raise NotImplementedError()
        if extension:
            self._extensions.append(extension)
        else:
            raise ValueError("argument can not be null")

    @property
    def experimental_options(self) -> dict:
        """
        :Returns: A dictionary of experimental options for chromium
        """
        raise NotImplementedError()
        return self._experimental_options

    def add_experimental_option(self, name: str, value: Union[str, int, dict, List[str]]) -> None:
        """Adds an experimental option which is passed to chromium.

        :Args:
          name: The experimental option name.
          value: The option value.
        """
        raise NotImplementedError()
        self._experimental_options[name] = value

    @property
    def headless(self) -> bool:
        """
        :Returns: True if the headless argument is set, else False
        """
        warnings.warn(
            "headless property is deprecated, instead check for '--headless' in arguments",
            DeprecationWarning,
            stacklevel=2,
        )
        return "--headless" in self._arguments

    @headless.setter
    def headless(self, value: bool) -> None:
        """Sets the headless argument Old headless uses a non-production
        browser and is set with `--headless`

        Native headless from v86 - v108 is set with `--headless=chrome`
        Native headless from v109+ is set with `--headless=new`
        :Args:
          value: boolean value indicating to set the headless option
        """
        warnings.warn(
            "headless property is deprecated, instead use add_argument('--headless') or add_argument('--headless=new')",
            DeprecationWarning,
            stacklevel=2,
        )
        args = {"--headless"}
        if value:
            self._arguments.extend(args)
        else:
            self._arguments = list(set(self._arguments) - args)

    def to_capabilities(self) -> dict:
        """
        Creates a capabilities with all the options that have been set
        :Returns: A dictionary with everything
        """
        caps = self._caps
        chrome_options = {}  # self.experimental_options.copy()
        if self.mobile_options:
            chrome_options.update(self.mobile_options)
        # chrome_options["extensions"] = self.extensions
        if self.binary_location:
            chrome_options["binary"] = self.binary_location
        chrome_options["args"] = self._arguments
        if self.debugger_address:
            chrome_options["debuggerAddress"] = self.debugger_address

        caps[self.KEY] = chrome_options

        return caps

    #
    # Options(ChromiumOptions) from here on
    #

    @property
    def default_capabilities(self) -> dict:
        return DesiredCapabilities.CHROME.copy()
