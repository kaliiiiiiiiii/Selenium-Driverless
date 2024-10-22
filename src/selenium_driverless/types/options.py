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

import os
import pathlib
import warnings
from abc import ABCMeta
import typing
from typing import Union, Optional, List
from selenium_driverless.scripts.prefs import prefs_to_json


# noinspection PyUnreachableCode,PyUnusedLocal
class Options(metaclass=ABCMeta):
    """
    the `webdriver.ChromeOptions` class

    .. warning::

        options should not be reused

    """

    use_extension: bool = True
    """
    don't add the chrome-extension by default
    
    .. warning::
        setting proxies and auth while running requires the extension to be added. 
        As an alternative, you might use ``--proxy-server=host:port`` and `Requests-interception <https://kaliiiiiiiiii.github.io/Selenium-Driverless/api/RequestInterception/#request-interception>`_ to provide auth
    """

    def __init__(self) -> None:

        self._single_proxy = None
        from selenium_driverless.utils.utils import IS_POSIX
        super().__init__()

        self._proxy = None
        # self.set_capability("pageLoadStrategy", "normal")
        self.mobile_options = None

        self._binary_location = None
        self._env = os.environ
        self._extension_paths = []
        self._extensions = []
        self._experimental_options = {}
        self._debugger_address = None
        self._user_data_dir = None
        self._downloads_dir = None
        self._arguments = []
        self._prefs = {
            'devtools': {
                'preferences': {
                    # always open devtools in undocked
                    'currentDockState': '"undocked"',
                    # always open devtools with console open
                    'panel-selectedTab': '"console"'}
            },
            "download_bubble": {
                # don't Show downloads when they're done
                "partial_view_enabled": False,
            },
            "in_product_help": {
                "snoozed_feature": {
                    "IPH_HighEfficiencyMode": {
                        # disable "memory saver"
                        # instead, limit number of open tabs
                        # https://github.com/milahu/aiohttp_chromium/blob/61fe3150ed032ef8aa99b23dddbedaa1929c229c/src/aiohttp_chromium/client.py#L1017-L1025
                        "is_dismissed": True,
                    }
                }
            },
            # disable password manager popup https://stackoverflow.com/a/46602329/20443541
            "credentials_enable_service": False,
            "profile": {"password_manager_enabled": False}
        }
        self._ignore_local_proxy = False
        self._auto_clean_dirs = True
        self._headless = False
        self._startup_url = "about:blank"

        self.add_arguments(
            "--no-first-run",  # disable first run page
            # '--disable-component-update',  # disable updates, breaks widevine
            '--no-service-autorun',  # don't start a service
            # don't auto-reload pages on network errors, https://github.com/milahu/aiohttp_chromium/blob/61fe3150ed032ef8aa99b23dddbedaa1929c229c/src/aiohttp_chromium/client.py#L1116C9-L1118
            "--disable-auto-reload",
            # some backgrounding tweaking
            '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding',
            '--disable-background-timer-throttling',
            '--disable-background-networking', '--no-pings',
            '--disable-infobars', '--disable-breakpad',  # some bars tweak
            "--no-default-browser-check",  # disable default browser message
            '--homepage=about:blank'  # set homepage
            "--wm-window-animations-disabled", "--animation-duration-scale=0",  # disable animations
            "--enable-privacy-sandbox-ads-apis",
            # ensure window.Fence, window.SharedStorage etc. exist, looks like chrome disables them when using automation
            "--disable-search-engine-choice-screen",  # for chrome>=127,
            # "--enable-field-trial-config"
            # https://source.chromium.org/chromium/chromium/src/+/main:components/variations/variations_url_constants.cc
            # "--variations-server-url=https://clientservices.googleapis.com/chrome-variations/seed"
        )
        if IS_POSIX:
            self.add_argument("--password-store=basic")

        self._is_remote = True

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

    def add_arguments(self, *arguments: str):
        """add multiple arguments

        :param arguments: arguments to add
        """
        for arg in arguments:
            self.add_argument(arg)

    @property
    def prefs(self) -> dict:
        """the preferences as json"""
        return self._prefs

    def update_pref(self, pref: str, value):
        """update a preference

        :param pref: name of the preference ("." dot path)
        :param value: the value to set the preference to
        """
        self._prefs.update(prefs_to_json({pref: value}))

    @property
    def user_data_dir(self) -> str:
        """the directory to save all browser data in.
        ``None`` (default) will temporarily create a directory in $temp
        """
        return self._user_data_dir

    @user_data_dir.setter
    def user_data_dir(self, _dir: str):
        self._user_data_dir = _dir
        if _dir:
            self.add_argument(f"--user-data-dir={_dir}")

    @property
    def downloads_dir(self):
        """the default directory to download files to.

        .. code-block:: python

            _dir = os.getcwd()+"/downloads"
            if not os.path.isdir(_dir):
                os.mkdir(_dir)
            options = webdriver.ChromeOptions()
            options.downloads_dir = _dir
            options.update_pref("plugins.always_open_pdf_externally", True)
            async with webdriver.Chrome(options=options) as driver:
                download_data = await driver.get('https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf', timeout=5)
                print(download_data.get("guid_file"))

        .. warning::
            path has to be absolute
        """
        return self._downloads_dir

    @downloads_dir.setter
    def downloads_dir(self, directory_path: str):
        if directory_path is None:
            self._downloads_dir = None
        else:
            _dir = str(pathlib.Path(directory_path))
            if os.path.isfile(_dir):
                raise OSError("path can't point to a file")
            elif os.path.isdir(_dir):
                pass
            else:
                os.mkdir(_dir)
            self._downloads_dir = _dir

    @property
    def headless(self) -> bool:
        """
        Whether chrome starts headless.
        defaults to ``False``
        """
        return self._headless

    @headless.setter
    def headless(self, value: bool) -> None:
        if (value is False) and self._headless:
            raise NotImplementedError("setting headless=True can't be undone in options atm")
        if value is True:
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

    @property
    def binary_location(self) -> str:
        """
        path to the Chromium binary
        """
        from selenium_driverless.utils.utils import find_chrome_executable
        if self._binary_location is None:
            self._binary_location = find_chrome_executable()
        return self._binary_location

    @binary_location.setter
    def binary_location(self, value: str) -> None:
        self._binary_location = value

    @property
    def env(self):
        """the env for ``subprocess.Popen, ``os.environ`` by default"""
        return self._env

    @env.setter
    def env(self, env):
        self._env = env

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

    @property
    def debugger_address(self) -> str:
        """
        The address of the remote devtools instance in format "host:port"
        Setting this value makes the driver connect to a remote browser instance (unless you set user-data-dir as well)
        """
        return self._debugger_address

    @debugger_address.setter
    def debugger_address(self, value: str) -> None:
        self._debugger_address = value

    @single_proxy.setter
    def single_proxy(self, proxy: str):
        self._single_proxy = proxy

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

        .. warning::

            Not Implemented yet
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

        .. warning::
            NotImplemented yet
        """
        raise NotImplementedError()
        return self._caps.get("acceptInsecureCerts", False)

    def ignore_local_proxy_environment_variables(self) -> None:
        """By calling this you will ignore HTTP_PROXY and HTTPS_PROXY from
        being picked up and used.

        .. warning::
            NotImplemented yet
        """
        raise NotImplementedError()
        self._ignore_local_proxy = True

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
