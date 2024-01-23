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

import os
import warnings
from abc import ABCMeta
import typing
from typing import Union, Optional, List

from selenium_driverless.utils.utils import sel_driverless_path
from selenium_driverless.scripts.prefs import prefs_to_json


# noinspection PyUnreachableCode,PyUnusedLocal
class Options(metaclass=ABCMeta):

    def __init__(self) -> None:

        self._single_proxy = None
        from selenium_driverless.utils.utils import find_chrome_executable, IS_POSIX
        super().__init__()

        self._proxy = None
        # self.set_capability("pageLoadStrategy", "normal")
        self.mobile_options = None

        self._binary_location = find_chrome_executable()
        self._extension_paths = []
        self._extensions = []
        self._experimental_options = {}
        self._debugger_address = None
        self._user_data_dir = None
        self._arguments = []
        self._prefs = {'devtools': {
            'preferences': {
                # always open devtools in undocked
                'currentDockState': '"undocked"',
                # always open devtools with console open
                'panel-selectedTab': '"console"'}
        }
        }
        self._ignore_local_proxy = False
        self._auto_clean_dirs = True
        self._headless = False
        self._startup_url = "about:blank"

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

        # noinspection SpellCheckingInspection
        self.add_argument('--disable-infobars')
        self.add_argument('--disable-breakpad')
        self.add_argument("--no-default-browser-check")
        self.add_argument('--homepage=about:blank')

        self._is_remote = True

        # extension
        self.add_extension(sel_driverless_path() + "files/mv3_extension")

    @property
    def auto_clean_dirs(self) -> bool or None:
        """if user-data-dir should be cleaned automatically
        defaults to True
        """
        return self._auto_clean_dirs

    @auto_clean_dirs.setter
    def auto_clean_dirs(self, enabled: bool = True) -> None:
        self._auto_clean_dirs = enabled

    def enable_mobile(
            self,
            android_package: str = "com.android.chrome",
            android_activity: Optional[str] = None,
            device_serial: Optional[str] = None,
    ) -> None:
        """Enables mobile browser use for browsers that support it.

        :param android_activity: The name of the android package to start
        :param android_package:
        :param device_serial:
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

    @property
    def single_proxy(self):
        """
        Set a single proxy to be applied.

        .. code-block:: python

            options = webdriver.ChromeOptions()
            options.single_proxy = "http://user1:passwrd1@example.proxy.com:5001/"

        .. warning::

            - Only supported when Chrome has been started with driverless or the extension at ``selenium_driverless/files/mv3_extension`` has been loaded into the browser.

            - ``Socks5`` doesn't support authentication due to `crbug#1309413 <https://bugs.chromium.org/p/chromium/issues/detail?id=1309413>`__.

        """

        return self._single_proxy

    @single_proxy.setter
    def single_proxy(self, proxy: str):
        self._single_proxy = proxy

    @property
    def prefs(self) -> dict:
        return self._prefs

    def update_pref(self, pref: str, value):
        self._prefs.update(prefs_to_json({pref: value}))

    @property
    def arguments(self) -> typing.List[str]:
        """
        used arguments for the chrome executable
        """
        return self._arguments

    def add_argument(self, argument: str):
        """Adds an argument for launching chrome

        :param argument: argument to add
        """
        import os
        if type(argument) is str:
            if argument[:16] == "--user-data-dir=":
                user_data_dir = argument[16:]
                if not os.path.isdir(user_data_dir):
                    os.makedirs(user_data_dir, exist_ok=True)
                self._user_data_dir = user_data_dir
            elif argument[:24] == "--remote-debugging-port=":
                port = int(argument[24:])
                if not self._debugger_address:
                    self._debugger_address = f"127.0.0.1:{port}"
                self._is_remote = False
            elif argument[:17] == "--load-extension=":
                extensions = argument[17:].split(",")
                self._extension_paths.extend(extensions)
                return
            elif argument[:10] == "--headless":
                self._headless = True
                if not (len(argument) > 10 and argument[11:] == "new"):
                    warnings.warn(
                        'headless without "--headless=new" might be buggy, makes you detectable & breaks proxies',
                        DeprecationWarning)
            self._arguments.append(argument)
        else:
            raise ValueError("argument has to be str")

    @property
    def user_data_dir(self) -> str:
        """the directory to save all browser data in.
        ``None`` (default) will temporarily create a directory in $temp
        """
        return self._user_data_dir

    @user_data_dir.setter
    def user_data_dir(self, _dir: str):
        self.add_argument(f"--user-data-dir={_dir}")

    def ignore_local_proxy_environment_variables(self) -> None:
        """By calling this you will ignore HTTP_PROXY and HTTPS_PROXY from
        being picked up and used."""
        raise NotImplementedError()
        self._ignore_local_proxy = True

    @property
    def binary_location(self) -> str:
        """
        path to the Chromium binary
        """
        return self._binary_location

    @binary_location.setter
    def binary_location(self, value: str) -> None:
        self._binary_location = value

    @property
    def debugger_address(self) -> str:
        """
        The address of the remote devtools instance
        Setting this value makes the driver connect to a remote browser instance.
        """
        return self._debugger_address

    @debugger_address.setter
    def debugger_address(self, value: str) -> None:
        self._debugger_address = value

    def add_extension(self, path: str) -> None:
        """Adds an extension to Chrome
        The extension can either be a compressed file (zip, crx, etc.) or extracted in a directory

        :param path: path to the extension
        """
        extension_to_add = os.path.abspath(os.path.expanduser(path))
        if os.path.exists(extension_to_add):
            self._extension_paths.append(extension_to_add)
        else:
            raise OSError("Path to the extension doesn't exist")

    def add_experimental_option(self, name: str, value: Union[str, int, dict, List[str]]) -> None:
        """Adds an experimental option which is passed to chromium.

        .. warning::
            only ``name="prefs"`` supported.
            This method is deprecated and will be removed. Use :obj:`ChromeOptions.update_pref` instead.

        :param name: The experimental option name.
        :param value: The option value.
        """
        if name == "prefs":
            self.prefs.update(prefs_to_json(value))
        else:
            raise NotImplementedError()

    @property
    def headless(self) -> bool:
        """
        Whether chrome starts headless.
        defaults to ``False``
        """
        return self._headless

    @headless.setter
    def headless(self, value: bool) -> None:
        self.add_argument("--headless=new")

    @property
    def startup_url(self) -> str:
        """
        the url the first tab loads.
        Defaults to ``about:blank``
        """
        return self._startup_url

    @startup_url.setter
    def startup_url(self, url: typing.Union[str, None]):
        if url is None:
            url = ""
        self._startup_url = url
