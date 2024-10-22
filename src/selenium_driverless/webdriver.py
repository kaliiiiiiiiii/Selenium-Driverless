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
# all modifications are licensed under the license provided at LICENSE.md

"""The WebDriver implementation."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import typing
import uuid
import warnings
import signal
from typing import List

# io
import asyncio

import cdp_socket.exceptions
import websockets

# interactions
from selenium_driverless.input.pointer import Pointer
from selenium_driverless.types.webelement import WebElement
from selenium_driverless.scripts.switch_to import SwitchTo

# contexts
from selenium_driverless.sync.context import Context as SyncContext
from selenium_driverless.types.context import Context

# Targets
from selenium_driverless.scripts.driver_utils import get_target
from selenium_driverless.types.target import Target, TargetInfo
from selenium_driverless.types.base_target import BaseTarget
from selenium_driverless.sync.base_target import BaseTarget as SyncBaseTarget

# others
from cdp_socket.utils.conn import get_json
from selenium_driverless.types.options import Options as ChromeOptions
from selenium_driverless.utils.utils import sel_driverless_path
from selenium_driverless.types import JSEvalException
from selenium_driverless import EXC_HANDLER


class Chrome:
    """Control the chromium based browsers without any driver."""
    port: int

    def __init__(
            self,
            options: ChromeOptions = None,
            timeout: float = 30,
            debug: bool = False,
            max_ws_size: int = 2 ** 27
    ) -> None:
        # noinspection GrazieInspection
        """Creates a new instance of the chrome target. Starts the service and
                then creates new instance of chrome target.

                .. code-block:: python

                    options = webdriver.ChromeOptions.rst()
                    async with webdriver.Chrome(options=options) as driver:
                        await driver.get('https://abrahamjuliot.github.io/creepjs/', wait_load=True)
                        print(await driver.title)

                :param options: this takes an instance of ChromeOptions.rst
                :param timeout: timeout in seconds to start chrome
                :param debug: redirect errors from the chromium process output (stderr) to console
                :param max_ws_size: maximum size for websocket messages in bytes. 2^27 ~= 130 MB by default
                """
        self._prefs = {}
        self._auth_interception_enabled = None
        self._mv3_extension = None
        self._extensions_incognito_allowed = None
        self._base_context = None
        self._stderr = None
        self._stderr_file = None
        self._process = None
        self._current_target = None
        self._host = None
        self._timeout = timeout
        self._loop: asyncio.AbstractEventLoop or None = None
        self.browser_pid: int or None = None
        self._base_target = None
        self._debug = debug
        # noinspection PyTypeChecker
        self._current_context: Context = None
        self._contexts: typing.Dict[str, Context] = {}
        self._temp_dir = tempfile.TemporaryDirectory(prefix="selenium_driverless_").name
        self._max_ws_size = max_ws_size

        self._auth = {}

        if not options:
            options = ChromeOptions()
        if not options.binary_location:
            from selenium_driverless.utils.utils import find_chrome_executable
            options.binary_location = find_chrome_executable()

        self._options: ChromeOptions = options
        self._is_remote = True
        self._is_remote = False
        self._has_incognito_contexts: bool = False
        self._started = False

    def __repr__(self):
        return f'<{type(self).__module__}.{type(self).__name__} (session="{self.current_target.id}")>'

    async def __aenter__(self):
        await self.start_session()
        return self

    def __enter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.quit(clean_dirs=self._options.auto_clean_dirs)

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __await__(self):
        return self.start_session().__await__()

    async def start_session(self):
        if not self._started:
            from selenium_driverless.utils.utils import read
            from selenium_driverless.utils.utils import is_first_run, get_default_ua, set_default_ua
            from selenium_driverless.scripts.prefs import read_prefs, write_prefs

            await is_first_run()
            user_agent = await get_default_ua()

            if self._options.use_extension:
                # extension
                self._options.add_extension(sel_driverless_path() + "files/mv3_extension")

            if not self._options.debugger_address:
                from selenium_driverless.utils.utils import random_port
                port = random_port()
                self._options._debugger_address = f"127.0.0.1:{port}"
                self._options.add_argument(f"--remote-debugging-port={port}")

            if self._options.headless and not self._is_remote:
                # patch useragent
                if user_agent:
                    self._options.add_argument(f"--user-agent={user_agent}")
                else:
                    warnings.warn("headless is detectable at first run")

            # handle prefs

            if self._options.user_data_dir:
                prefs_path = self._options.user_data_dir + "/Default/Preferences"
                if os.path.isfile(prefs_path):
                    self._prefs = await read_prefs(prefs_path)
                else:
                    os.makedirs(os.path.dirname(prefs_path), exist_ok=True)

                # write prefs
                self._prefs.update(self._options.prefs)
                await write_prefs(self._prefs, prefs_path)
            elif self._options.user_data_dir is None:
                self._options.add_argument(
                    "--user-data-dir=" + self._temp_dir + "/data_dir")
                prefs_path = self._options.user_data_dir + "/Default/Preferences"
                os.makedirs(os.path.dirname(prefs_path), exist_ok=True)

                # write prefs
                self._prefs.update(self._options.prefs)
                await write_prefs(self._prefs, prefs_path)

            # noinspection PyProtectedMember
            # handle extensions
            if self._options._extension_paths:
                import zipfile
                extension_paths = []
                loop = asyncio.get_running_loop()

                # noinspection PyProtectedMember
                def extractall():
                    for _path in self._options._extension_paths:
                        if os.path.isfile(_path):
                            with zipfile.ZipFile(_path, 'r') as zip_ref:
                                _path = self._temp_dir + f"/{uuid.uuid4().hex}"
                                zip_ref.extractall(_path)
                        extension_paths.append(_path)

                await loop.run_in_executor(None, extractall)

                self._options.arguments.append(f"--load-extension=" + ','.join(extension_paths))
            self._options._extension_paths = []

            if self._options.startup_url:
                self._options.add_argument(self._options.startup_url)
            self._options._startup_url = None

            options = self._options

            # noinspection PyProtectedMember
            self._is_remote = self._options._is_remote

            if not self._is_remote:
                path = options.binary_location
                args = options.arguments
                if self._debug:
                    self._stderr = sys.stderr
                else:
                    self._stderr = tempfile.TemporaryFile(prefix="selenium_driverless")
                    self._stderr_file = self._stderr
                self._process = subprocess.Popen(
                    [path, *args],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=self._stderr,
                    close_fds=True,
                    preexec_fn=os.setsid if os.name == 'posix' else None,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
                    shell=False,
                    text=True,
                    env=self._options.env
                )

                host, port = self._options.debugger_address.split(":")
                port = int(port)
                if port == 0:
                    path = self._options.user_data_dir + "/DevToolsActivePort"
                    while not os.path.isfile(path):
                        await asyncio.sleep(0.1)
                    port = await read(path, sel_root=False)
                    port = int(port.split("\n")[0])
                    self._options.debugger_address = f"127.0.0.1:{port}"

            host, port = self._options.debugger_address.split(":")
            self.port = int(port)
            self._host = f"{host}:{self.port}"
            if self._loop:
                self._base_target = await SyncBaseTarget(host=self._host, is_remote=self._is_remote,
                                                         timeout=self._timeout, loop=self._loop,
                                                         max_ws_size=self._max_ws_size)
            else:
                self._base_target = await BaseTarget(host=self._host, is_remote=self._is_remote,
                                                     timeout=self._timeout, loop=self._loop,
                                                     max_ws_size=self._max_ws_size)

            # fetch useragent at first headless run
            # noinspection PyUnboundLocalVariable
            if not self._is_remote:
                res = await self._base_target.execute_cdp_cmd("Browser.getVersion")
                user_agent = res["userAgent"]
                user_agent = user_agent.replace("HeadlessChrome", "Chrome")
                await set_default_ua(user_agent)

            if not self._is_remote:
                # noinspection PyUnboundLocalVariable
                self.browser_pid = self._process.pid
            targets = await get_json(self._host, timeout=self._timeout)
            for target in targets:
                if target["type"] == "page" and not target["url"].startswith("chrome-extension://"):
                    target_id = target["id"]
                    self._current_target = await get_target(target_id=target_id, host=self._host,
                                                            loop=self._loop, is_remote=self._is_remote, timeout=10,
                                                            max_ws_size=self._max_ws_size, driver=self, context=None)

                    # handle the context
                    if self._loop:
                        context = await SyncContext(base_target=self._current_target, driver=self, loop=self._loop,
                                                    max_ws_size=self._max_ws_size)
                    else:
                        context = await Context(base_target=self._current_target, driver=self, loop=self._loop,
                                                max_ws_size=self._max_ws_size)
                    _id = context.context_id
                    self._current_target._context = context

                    def remove_context():
                        if _id in self._contexts:
                            del self._contexts[_id]
                        self._base_context = None

                    # noinspection PyProtectedMember
                    context._closed_callbacks.append(remove_context)
                    self._current_context = context
                    self._base_context = context
                    self._contexts[_id] = context
                    break
            await self.execute_cdp_cmd("Emulation.setFocusEmulationEnabled", {"enabled": True})
            if self._options.single_proxy:
                await self.set_single_proxy(self._options.single_proxy)
            downloads_dir = self._options.downloads_dir
            if self._options.downloads_dir:
                # ensure download events are dispatched
                await self.set_download_behaviour("allowAndName", downloads_dir)
            else:
                await self.set_download_behaviour("default")
            self._started = True
        return self

    @property
    async def frame_tree(self) -> dict:
        """
        **async**
        all nested frames within the current target
        """
        return await self.current_context.frame_tree

    @property
    async def targets(self) -> typing.Dict[str, TargetInfo]:
        """
        **async**
        all targets within the current context
        """
        return await self.current_context.targets

    @property
    async def contexts(self) -> typing.Dict[str, Context]:
        """
        **async**
        all (incognito) contexts on Chrome.
        """
        targets = await self.get_targets(context_id=None)
        contexts = {}
        for info in targets.values():
            _id = info.browser_context_id
            if _id:
                context = self._contexts.get(_id)
                if not context:
                    if self._loop:
                        context = await SyncContext(base_target=self._current_target, context_id=_id,
                                                    loop=self._loop, max_ws_size=self._max_ws_size, driver=self)
                    else:
                        context = await Context(base_target=self._current_target, context_id=_id,
                                                loop=self._loop, max_ws_size=self._max_ws_size, driver=self)
                contexts[_id] = context
        self._contexts.update(contexts)
        return self._contexts

    async def new_context(self, proxy_bypass_list: typing.List[str] = None, proxy_server: str = True,
                          universal_access_origins: typing.List[str] = None, url: str = "about:blank") -> Context:
        """
        creates a new (incognito) context

        :param url: the url the first tab will start at. "about:blank" by default
        :param universal_access_origins: An optional list of origins to grant unlimited cross-origin access to. Parts of the URL other than those constituting origin are ignored

        .. warning::
            The proxy parameter doesn't work on Windows due to `crbug#1310057 <https://bugs.chromium.org/p/chromium/issues/detail?id=1310057>`__.

        .. code block:: python
            await driver.set_auth("username", "password", "localhost:5000")
            context = await driver.new_context(proxy_bypass_list=["localhost"], proxy_server="http://localhost:5000")

        :param proxy_server: a proxy-server to use for the context
        :param proxy_bypass_list: a list of proxies to ignore
        """
        await self.ensure_extensions_incognito_allowed()
        if proxy_bypass_list is None:
            proxy_bypass_list = ["localhost"]
        if proxy_server is None:
            proxy_server = ""
        args = {"disposeOnDetach": False}
        if proxy_bypass_list:
            args["proxyBypassList"] = ",".join(proxy_bypass_list)
        if not (proxy_server is True):
            args["proxyServer"] = proxy_server
        if universal_access_origins:
            args["originsWithUniversalNetworkAccess"] = universal_access_origins

        # create context ensuring extension racing conditions
        self._auth_interception_enabled = False
        has_incognito_ctxs = not (not self._has_incognito_contexts)
        self._has_incognito_contexts = True
        mv3_ext = await self.mv3_extension
        self._mv3_extension = None

        try:
            res = await self.base_target.execute_cdp_cmd("Target.createBrowserContext", args)
        except Exception as e:
            self._mv3_extension = mv3_ext
            self._auth_interception_enabled = True
            self._has_incognito_contexts = has_incognito_ctxs
            raise e

        _id = res["browserContextId"]
        if self._loop:
            context = await SyncContext(base_target=self._base_target, context_id=_id, loop=self._loop,
                                        is_incognito=True,
                                        max_ws_size=self._max_ws_size, driver=self)
        else:
            context = await Context(base_target=self._base_target, context_id=_id, loop=self._loop,
                                    is_incognito=True, max_ws_size=self._max_ws_size,
                                    driver=self)
        self._contexts[_id] = context

        def remove_context():
            if _id in self._contexts:
                del self._contexts[_id]

        # noinspection PyProtectedMember
        context._closed_callbacks.append(remove_context)
        await context.switch_to.new_window("window", activate=False, url=url)
        tabs = await context.get_targets(_type="page", context_id=_id)
        context._current_target = list(tabs.values())[0].Target
        context._current_target._timeout = 5

        # reload auth & extension target to fix non-applied auth
        if self._auth:
            self._mv3_extension = None
            while True:
                # ensure racing conditions with extension
                try:
                    mv3_target = await self.mv3_extension
                    self._auth_interception_enabled = False
                    await self._ensure_auth_interception(timeout=0.5, set_flag=False)
                    await mv3_target.execute_script("globalThis.authCreds = arguments[0]", self._auth, timeout=0.5,
                                                    unique_context=False)
                except (asyncio.TimeoutError, TimeoutError):
                    await asyncio.sleep(0.1)
                    self._mv3_extension = None
                else:
                    self._auth_interception_enabled = True
                    self._mv3_extension = mv3_target
                    return context
        return context

    async def get_targets(self,
                          _type: typing.Literal["page", "background_page", "service_worker", "browser", "other"] = None,
                          context_id: str or None = "self") -> typing.Dict[str, TargetInfo]:
        """
        get all targets within the current context
        :param _type: filter by target type
        :param context_id: if ``None``, this function returns all targets for all contexts.
        """
        return await self.current_context.get_targets(_type=_type, context_id=context_id)

    @property
    def current_target(self) -> Target:
        """
        the current Target
        """
        if self.current_context:
            return self.current_context.current_target
        return self._current_target

    @property
    def base_target(self) -> BaseTarget:
        """
        The connection handle for the global connection to Chrome

        .. warning::
            only the bindings for using the CDP-protocol on BaseTarget supported
        """
        return self._base_target

    @property
    async def mv3_extension(self, timeout: float = 10) -> Target:
        """
        **async** the target for the background script of the by default loaded Chrome-extension (manifest-version==3)

        .. note:
            for incognito context, the extension uses the "spanning" configuration, as there isn't a way to debug "split" mode over CDP
        """
        if self._has_incognito_contexts:
            await self.ensure_extensions_incognito_allowed()
        if not self._mv3_extension:
            import re
            import time
            start = time.perf_counter()
            extension_target = None
            while not extension_target:
                targets = await self.get_targets(context_id=None)
                for target in targets.values():
                    if target.type == "service_worker":
                        if re.fullmatch(
                                r"chrome-extension://(.*)/"
                                r"driverless_background_mv3_243ffdd55e32a012b4f253b2879af978\.js",
                                target.url):
                            extension_target = target.Target
                            break
                if not extension_target:
                    if (time.perf_counter() - start) > timeout:
                        raise asyncio.TimeoutError(f"Couldn't find mv3 extension within {timeout} seconds")
            while True:
                try:
                    # fix WebRTC leak
                    await extension_target.execute_script(
                        "chrome.privacy.network.webRTCIPHandlingPolicy.set(arguments[0])",
                        {"value": "disable_non_proxied_udp"}, timeout=2, unique_context=False)
                except (asyncio.TimeoutError, TimeoutError):
                    await asyncio.sleep(0.2)
                    return await self.mv3_extension
                except JSEvalException:
                    await asyncio.sleep(0.2)
                except cdp_socket.exceptions.CDPError as e:
                    if e.code == -32000 and e.message == 'Could not find object with given id':
                        await asyncio.sleep(0.2)
                else:
                    break
            self._mv3_extension = extension_target
        return self._mv3_extension

    async def ensure_extensions_incognito_allowed(self):
        """
        ensure that all installed Chrome-extensions are allowed in incognito context.

        .. warning::
            Generally, the extension decides whether to use the ``split``, ``spanning`` or ``not_allowed`` configuration.
            For changing this behaviour, you'll have to modify the ``manifest.json`` file within the compressed extension or directory.
            See `developer.chrome.com/docs/extensions/reference/manifest/incognito <https://developer.chrome.com/docs/extensions/reference/manifest/incognito?hl=en>`__.
        """
        if not self._extensions_incognito_allowed:
            self._extensions_incognito_allowed = True
            # noinspection PyTypeChecker
            page = None
            try:
                base_ctx = self._base_context
                page: Context = await base_ctx.new_window("tab", "chrome://extensions", activate=False)
                script = """
                    async function make_global(){
                        const extensions = await chrome.developerPrivate.getExtensionsInfo();
                        extensions.forEach( async function(extension)  {
                            chrome.developerPrivate.updateExtensionConfiguration({
                                extensionId: extension.id,
                                incognitoAccess: true
                            })
                        });
                    };
                    await make_global()
                """
                await asyncio.sleep(0.1)
                await page.eval_async(script, timeout=10, unique_context=False)
            except Exception as e:
                EXC_HANDLER(e)
                self._extensions_incognito_allowed = False
                if page:
                    await page.close()
                await self.ensure_extensions_incognito_allowed()
            self._extensions_incognito_allowed = True
            await page.close()

    @property
    def base_context(self) -> Context:
        """
        the Context which isn't incognito
        """
        return self._base_context

    @property
    def downloads_dir(self):
        """the current downloads directory for the current context"""
        return self.base_target.downloads_dir_for_context(context_id="DEFAULT")

    async def set_download_behaviour(self, behaviour: typing.Literal["deny", "allow", "allowAndName", "default"],
                                     path: str = None):
        """set the download behaviour

        :param behaviour: the behaviour to set the downloading to
        :param path: the path to the default download directory

        .. warning::
            setting ``behaviour=allow`` instead of ``allowAndName`` can cause some bugs

        """
        await self.current_context.set_download_behaviour(behaviour, path)

    @property
    def current_context(self) -> Context:
        """
        the current context switched to
        """
        if not self._current_context:
            if self._contexts:
                return list(self._contexts.values())[0]
        return self._current_context

    @property
    async def _isolated_context_id(self):
        # noinspection PyProtectedMember
        return await self.current_context._isolated_context_id

    async def get_target(self, target_id: str = None, timeout: float = 2) -> Target:
        """
        get a Target by TargetId for advanced usage of the CDP protocol
        :param target_id:
        :param timeout: timeout in seconds for connecting to the target if it's not tracked already
        """
        if not target_id:
            return self.current_target
        return await self.current_context.get_target(target_id=target_id, timeout=timeout)

    async def get_target_for_iframe(self, iframe: WebElement) -> Target:
        """
        get the Target for a specific iframe

        .. warning::
            only cross-iframes have a Target due to `OOPIF <https://www.chromium.org/developers/design-documents/oop-iframes/>`__. See `site-isolation <https://www.chromium.org/Home/chromium-security/site-isolation/>`__
            For a general solution, have a look at ``WebElement.content_document`` instead

        :param iframe: the iframe to get the Target for
        """
        return await self.current_target.get_target_for_iframe(iframe=iframe)

    async def get_targets_for_iframes(self, iframes: typing.List[WebElement]) -> typing.List[Target]:
        """
        returns a list of targets for iframes
        see ``webdriver.Chrome.get_target_for_iframe`` for more information

        :param iframes: the iframe to get the targets for
        """
        return await self.current_target.get_targets_for_iframes(iframes=iframes)

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

    async def get(self, url: str, referrer: str = None, wait_load: bool = True, timeout: float = 30) -> typing.Union[
        None, dict]:
        """Loads a web page in the current Target

        :param url: the url to load.
        :param referrer: the referrer to load the page with
        :param wait_load: whether to wait for the webpage to load
        :param timeout: the maximum time in seconds for waiting on load

        returns the same as :func:`Target.wait_download <selenium_driverless.types.target.Target.wait_download>` if the url initiates a download
        """
        return await self.current_target.get(url=url, referrer=referrer, wait_load=wait_load, timeout=timeout)

    @property
    async def title(self) -> str:
        """**async** the title of the current target"""
        target = await self.current_target_info
        return target.title

    @property
    def current_pointer(self) -> Pointer:
        """the :class:`Pointer <selenium_driverless.input.pointer.Pointer>` for this target"""
        target = self.current_target
        return target.pointer

    async def send_keys(self, text: str):
        """
        send text & keys to the current target

        :param text: the text to send
        """
        await self.current_target.send_keys(text)

    async def execute_raw_script(self, script: str, *args, await_res: bool = False,
                                 serialization: typing.Literal["deep", "json", "idOnly"] = "deep",
                                 max_depth: int = None, timeout: float = 2, execution_context_id,
                                 unique_context: bool = True):
        """executes a JavaScript on ``GlobalThis`` such as

        .. code-block:: js

            function(...arguments){return document}

        :param script: the script as a string
        :param args: the argument which are passed to the function. Those can be either json-serializable or a RemoteObject such as WebElement
        :param await_res: whether to await the function or the return value of it
        :param serialization: can be one of ``deep``, ``json``, ``idOnly``
        :param max_depth: The maximum depth objects get serialized.
        :param timeout: the maximum time to wait for the execution to complete
        :param execution_context_id: the execution context id to run the JavaScript in. Exclusive with unique_context
        :param unique_context: whether to use an isolated context to run the Script in.

        see `Runtime.callFunctionOn <https://chromedevtools.github.io/devtools-protocol/tot/Runtime/#method-callFunctionOn>`_
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
                                   serialization: str = None, timeout: float = 2, execution_context_id: str = None,
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
                         serialization: str = None, timeout: float = 2, execution_context_id: str = None,
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
        """**async** current URL of the current Target
        """
        target = self.current_target
        return await target.url

    @property
    async def page_source(self) -> str:
        """**async** html of the current page.
        """
        target = self.current_target
        return await target.page_source

    async def close(self, timeout: float = 2) -> None:
        """Closes the current target (only works for tabs).
        :param timeout: timeout in seconds for the tab to close
        """
        await self.current_target.close(timeout=timeout)

    async def focus(self):
        """focuses the current target (only works for tabs)
        """
        await self.current_target.focus()

    async def quit(self, timeout: float = 30, clean_dirs: bool = True) -> None:
        """Closes Chrome
        :param timeout: the maximum time waiting for chrome to quit correctly
        :param clean_dirs: whether to clean out the user-data-dir directory
        """
        from selenium_driverless import EXC_HANDLER

        loop = asyncio.get_running_loop()

        def clean_dirs_sync(dirs: typing.List[str]):
            for _dir in dirs:
                while os.path.isdir(_dir):
                    shutil.rmtree(_dir, ignore_errors=True)

        if self._started:
            start = time.perf_counter()
            # noinspection PyUnresolvedReferences
            try:
                # assumption: chrome is still running
                await self.base_target.execute_cdp_cmd("Browser.close", timeout=7)
            except websockets.ConnectionClosedError:
                pass
            except Exception as e:
                EXC_HANDLER(e)
            if not self._is_remote:
                if self._process is not None:
                    # assumption: chrome is being shutdown manually or programmatically
                    try:
                        await loop.run_in_executor(None, lambda: self._process.wait(timeout))
                    except Exception as e:
                        EXC_HANDLER(e)
                    else:
                        self._process = None
                try:
                    # assumption: chrome hasn't closed within timeout, killing with force
                    # wait for process to be killed
                    if self._process is not None:
                        if os.name == 'posix':
                            os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                        else:
                            self._process.terminate()
                        try:
                            await loop.run_in_executor(None, lambda: self._process.wait(timeout))
                        except subprocess.TimeoutExpired:
                            if os.name == 'posix':
                                os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                            else:
                                self._process.kill()
                except Exception as e:
                    EXC_HANDLER(e)
                finally:
                    self._started = False
                    if self._stderr_file:
                        try:
                            self._stderr.close()
                        except Exception as e:
                            EXC_HANDLER(e)

                    # clean temp dir for extensions etc
                    try:
                        await asyncio.wait_for(
                            # wait for
                            loop.run_in_executor(None,
                                                 lambda: clean_dirs_sync(
                                                     [self._temp_dir])),
                            timeout=max(5, int(timeout - (time.perf_counter() - start))))
                    except Exception as e:
                        EXC_HANDLER(e)

                    if clean_dirs:
                        # clean user-data-dir for chrome
                        try:
                            await asyncio.wait_for(
                                # wait for
                                loop.run_in_executor(None,
                                                     lambda: clean_dirs_sync(
                                                         [self._options.user_data_dir])),
                                timeout=max(5, int(timeout - (time.perf_counter() - start))))
                        except Exception as e:
                            warnings.warn(
                                "driver hasn't quit correctly, "
                                "files might be left in your temp folder & chrome might still be running",
                                ResourceWarning)
                            raise e

    def __del__(self):
        try:
            if self._started:
                warnings.warn(
                    "driver hasn't quit correctly, "
                    "files might be left in your temp folder & chrome might still be running",
                    ResourceWarning)
        except AttributeError:
            pass

    @property
    async def current_target_info(self) -> TargetInfo:
        """**async** TargetInfo of the current target"""
        return await self.current_target.info

    @property
    def current_window_handle(self) -> str:
        """current TargetId

        .. warning::

            this is deprecated and will be removed
            use ``webdriver.Chrome.current_target.id`` instead
        """
        warnings.warn(f'"webdriver.Chrome.current_window_handle" is deprecated and will be removed\n'
                      'use "webdriver.Chrome.current_target.id" instead', DeprecationWarning)
        if self.current_target:
            return self.current_target.id

    @property
    async def current_window_id(self):
        """**async** the ``WindowId`` of the window the current Target belongs to
        """
        result = await self.execute_cdp_cmd("Browser.getWindowForTarget", {"targetId": self.current_target.id})
        return result["windowId"]

    @property
    async def window_handles(self) -> List[TargetInfo]:
        """**async** TargetInfo on all tabs in the current context

        .. warning::

            the tabs aren't ordered by position in the window. Do not rely on the index, but iterate and filter them.
        """
        warnings.warn(
            "the tabs aren't ordered by position in the window. Do not rely on the index, but iterate and filter them.")
        tabs = []
        targets = await self.targets
        for info in list(targets.values()):
            if info.type == "page":
                tabs.append(info)
        return tabs

    async def new_window(self, type_hint: typing.Literal["tab", "window"] = "tab", url="",
                         activate: bool = True) -> Target:
        """Creates a new window or tab in the current context

        :param type_hint: whether to create a tab or window
        :param url: the url which the new window should start on. Defaults to about:blank
        :param activate: whether to explicitly activate/focus the window

        .. code-block:: python

            new_target = driver.new_window('tab')
        """
        return await self.current_context.new_window(type_hint=type_hint, url=url, activate=activate)

    async def set_window_state(self, state: typing.Literal["normal", "minimized", "maximized", "fullscreen"]):
        """sets the window state on the window the current Target belongs to
        :param state: the state to set
        """
        window_id = await self.current_window_id
        bounds = {"windowState": state}
        await self.execute_cdp_cmd("Browser.setWindowBounds", {"bounds": bounds, "windowId": window_id})

    async def normalize_window(self):
        """Normalizes the window position and size on the window the current Target belongs to
        """
        await self.set_window_state("normal")

    async def maximize_window(self) -> None:
        """Maximizes the window the current Target belongs to"""
        await self.set_window_state("maximized")

    async def fullscreen_window(self) -> None:
        """enters fullscreen on the window the current Target belongs to"""
        await self.set_window_state("fullscreen")

    async def minimize_window(self) -> None:
        """minimizes the window the current Target belongs to.

        .. warning::

            Minimizing isn't recommended as it can throttle some functionalities in chrome.
        """
        await self.set_window_state("minimized")

    # noinspection PyUnusedLocal
    async def print_page(self) -> str:
        """Prints the page (current target => tab) to PDF
        """
        target = self.current_target
        return await target.print_page()

    @property
    def switch_to(self) -> SwitchTo:
        """SwitchTo handle
        """
        return self.current_context.switch_to

    # Navigation
    async def back(self) -> None:
        """Goes one step backward in the browser history on the current target (has to be a tab).
        """
        await self.current_target.back()

    async def forward(self) -> None:
        """Goes one step forward in the browser history on the current target (has to be a tab).
        """
        await self.current_target.forward()

    async def refresh(self) -> None:
        """Refreshes the current tab (target).
        """
        await self.current_target.refresh()

    # Options
    async def get_cookies(self) -> List[dict]:
        """list of cookies for the current tab
        """
        return await self.current_target.get_cookies()

    async def get_cookie(self, name) -> typing.Optional[typing.Dict]:
        """Get a single cookie by name. Returns the cookie if found, None if
        not.

        :param name: name of the cookie
        """
        return await self.current_target.get_cookie(name=name)

    async def delete_cookie(self, name: str, url: str = None, domain: str = None,
                            path: str = None) -> None:
        """Deletes a single cookie with the given name in the current tab.

        :param name: name of the cookie to delete
        :param url: url of the cookie
        :param domain: domain of the cookie
        :param path: path of the cookie
        """
        return await self.current_target.delete_cookie(name=name, url=url, domain=domain, path=path)

    async def delete_all_cookies(self) -> None:
        """Delete all cookies in the current (incognito-) context.
        """
        await self.current_target.delete_all_cookies()

    # noinspection GrazieInspection
    async def add_cookie(self, cookie_dict: dict) -> None:
        """Adds a cookie in the current (incognito-) context

        :param cookie_dict: see `Network.CookieParam <https://chromedevtools.github.io/devtools-protocol/tot/Network/#type-CookieParam>`__
        """
        await self.current_target.add_cookie(cookie_dict=cookie_dict)

    # Timeouts
    @staticmethod
    async def sleep(time_to_wait) -> None:
        # noinspection GrazieInspection
        """sleep
                .. note::
                    use this one instead of time.sleep in the sync version.

                :param time_to_wait: time in seconds to sleep
                """
        await asyncio.sleep(time_to_wait)

    # noinspection PyUnusedLocal
    async def find_element(self, by: str, value: str, timeout: float or None = None) -> WebElement:
        """find an element in the current target

        :param by: one of the locators at :func:`By <selenium_driverless.types.by.By>`
        :param value: the actual query to find the element by
        :param timeout: how long to wait for the element to exist
        """
        return await self.current_target.find_element(by=by, value=value, timeout=timeout)

    async def find_elements(self, by: str, value: str, timeout: float = 3) -> typing.List[WebElement]:
        """find multiple elements in the current target

        :param by: one of the locators at :func:`By <selenium_driverless.types.by.By>`
        :param value: the actual query to find the elements by
        :param timeout: how long to wait for not being in a page reload loop in seconds
        """
        return await self.current_target.find_elements(by=by, value=value, timeout=timeout)

    async def search_elements(self, query: str) -> typing.List[WebElement]:
        """
        find elements similarly to how "CTRL+F" in the DevTools Console works

        :param query: Plain text to find elements with
        """
        return await self.current_target.search_elements(query=query)

    async def get_screenshot_as_file(self, filename: str) -> None:
        """Saves a screenshot of the current tab to a PNG image file.
        :param filename: The path you wish to save your screenshot to. should end with a `.png` extension.

        .. code-block:: python

            driver.get_screenshot_as_file('screenshots/test.png')
        """
        return await self.current_target.get_screenshot_as_file(filename=filename)

    async def save_screenshot(self, filename) -> None:
        """alias to :func: `driver.get_screenshot_as_file <selenium_driverless.webdriver.Chrome.get_screenshot_as_file>`"""
        return await self.get_screenshot_as_file(filename)

    async def get_screenshot_as_png(self) -> bytes:
        """Gets the screenshot of the current tab as a binary data.
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
    async def set_window_size(self, width: int, height: int) -> None:
        """Sets the width and height of the window, the current tab is within (unless ``windowHandle`` specified)

        :param width: the width in pixels to set the window to
        :param height: the height in pixels to set the window to
        """
        await self.set_window_rect(width=int(width), height=int(height))

    # noinspection PyPep8Naming
    async def get_window_size(self) -> dict:
        """Gets the width and height of the current window.

        returns something like:
        .. code-block: json

            {"width":1280, "height":720}
        """
        size = await self.get_window_rect()

        if size.get("value"):
            size = size["value"]

        return {k: size[k] for k in ("width", "height")}

    # noinspection PyPep8Naming
    async def set_window_position(self, x: int, y: int) -> dict:
        """Sets the x,y position of the window, the current tab is in.

        :param x: the x-coordinate in pixels to set the window position
        :param y: the y-coordinate in pixels to set the window position
        """
        return await self.set_window_rect(x=int(x), y=int(y))

    # noinspection PyPep8Naming
    async def get_window_position(self) -> dict:
        """Gets the x,y position of the window, the current tab is in.

        returns something like:
        .. code-block: json

            {"x":0, "y":0}
        """
        position = await self.get_window_rect()

        return {k: position[k] for k in ("x", "y")}

    async def get_window_rect(self) -> dict:
        """Gets the x, y, with and height coordinates of the window, the current tab is in.

        returns something like:
        .. code-block: json

            {"x":0, "y":0,
            "width":1280, "height":720,
            "windowState":"normal"
            }

        .. note::

            ``windowState`` can be one of "normal", "minimized", "maximized", "fullscreen"
        """
        json = await self.execute_cdp_cmd("Browser.getWindowBounds", {"windowId": await self.current_window_id})
        json = json["bounds"]
        json["x"] = json["left"]
        del json["left"]
        json["y"] = json["top"]
        del json["top"]
        return json

    async def set_window_rect(self, x=None, y=None, width=None, height=None) -> dict:
        """Sets the x, y, width and height coordinates of the window the current target is in.

        :param x: the x-coordinate in pixels to set the window position
        :param y: the y-coordinate in pixels to set the window position
        :param width: the width in pixels to set the window to
        :param height: the height in pixels to set the window to

        .. note::

            either x and y or with and height have to be specified
        """

        if (x is None and y is None) and (height is None and width is None):
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

        returns a dict like:

        .. code-block:: python

            {"latency": 4, "download_throughput": 2, "upload_throughput": 2,
            "offline": False}
        """
        return await self.current_target.get_network_conditions()

    # noinspection SpellCheckingInspection
    async def set_network_conditions(self, offline: bool, latency: int, download_throughput: int,
                                     upload_throughput: int,
                                     connection_type: typing.Literal[
                                         "none", "cellular2g", "cellular3g", "cellular4g", "bluetooth", "ethernet", "wifi", "wimax", "other"]) -> None:
        # noinspection GrazieInspection
        """Sets Chromium network emulation settings.

        :param offline:
        :param latency:  additional latency in ms
        :param download_throughput: maximum throughput, 500 * 1024 for example
        :param upload_throughput: maximum throughput, 500 * 1024 for example
        :param connection_type: the connection type

        .. note::

            'throughput' can be used to set both (for download and upload).
        """
        return await self.current_target.set_network_conditions(offline=offline, latency=latency,
                                                                download_throughput=download_throughput,
                                                                upload_throughput=upload_throughput,
                                                                connection_type=connection_type)

    async def delete_network_conditions(self) -> None:
        """Resets Chromium network emulation settings."""
        await self.current_target.delete_network_conditions()

    async def set_permissions(self, name: str, value: typing.Literal["granted", "denied", "prompt"],
                              origin: str = None) -> None:
        """Sets Applicable Permission

        :param name: The item to set the permission on.
        :param value: The value to set on the item
        :param origin: the origin the permission for. Applies to any origin if not set

        .. code-block:: python

            target.set_permissions('clipboard-read', 'denied')
        """
        settings = ["granted", "denied", "prompt"]
        if value not in settings:
            raise ValueError(f"value needs to be within {settings}, but got {value}")
        args = {"permission": {"name": name}, "setting": value}
        if origin:
            args["origin"] = origin
        await self.execute_cdp_cmd("Browser.setPermission", args)

    async def set_proxy(self, proxy_config):
        # noinspection GrazieInspection
        """ set a proxy dynamically

        Example parameters:

        .. code-block:: python

            proxy_config = {
                "mode": "fixed_servers",
                "rules": {
                    "proxyForHttp": {
                        "scheme": scheme,
                        "host": host,
                        "port": port
                    },
                    "proxyForHttps": {
                        "scheme": scheme,
                        "host": host,
                        "port": port
                    },
                    "proxyForFtp": {
                        "scheme": scheme,
                        "host": host,
                        "port": port
                    },
                    "fallbackProxy": {
                        "scheme": scheme,
                        "host": host,
                        "port": port
                    },
                    "bypassList": ["<local>"]
                }
            }

        :param proxy_config: see `developer.chrome.com/docs/extensions/reference/proxy <https://developer.chrome.com/docs/extensions/reference/proxy/>`__ for reference

        for authentification, see :func:`webdriver.Chrome.set_auth <selenium_driverless.webdriver.Chrome.set_auth>`
        """
        extension = await self.mv3_extension
        await extension.eval_async("await chrome.proxy.settings.set(arguments[0])",
                                   {"value": proxy_config, "scope": 'regular'}, unique_context=False)

    async def set_single_proxy(self, proxy: str, bypass_list=None):
        """
        Set a single proxy dynamically to be applied in all contexts.

        .. code-block:: python

            "http://user1:passwrd1@example.proxy.com:5001/"

        .. warning::

            - Only supported when Chrome has been started with driverless or the extension at ``selenium_driverless/files/mv3_extension`` has been loaded into the browser.

            - ``Socks5`` doesn't support authentication due to `crbug#1309413 <https://bugs.chromium.org/p/chromium/issues/detail?id=1309413>`__.

        """

        # parse scheme
        proxy = proxy.split("://")
        if len(proxy) == 2:
            scheme, proxy = proxy
        else:
            scheme = None
            proxy = proxy[0]

        proxy = proxy.split("@")
        if len(proxy) == 2:
            creds, proxy = proxy
        else:
            proxy = proxy[0]
            creds = None

        # parse host & port
        proxy = proxy.split(":")
        if len(proxy) == 2:
            host, port = proxy
            port = int(port.replace("/", ""))
        else:
            port = None
            host = proxy[0]

        rule = {"host": host}
        if scheme:
            rule["scheme"] = scheme
        if port:
            rule["port"] = port
        if bypass_list is None:
            bypass_list = ["<local>"]
        proxy_config = {
            "mode": "fixed_servers",
            "rules": {
                "proxyForHttp": rule,
                "proxyForHttps": rule,
                "proxyForFtp": rule,
                "fallbackProxy": rule,
                "bypassList": bypass_list
            }
        }
        await self.set_proxy(proxy_config)
        if creds:
            user, passw = creds.split(":")
            await self.set_auth(user, passw, f"{host}:{port}")

    async def clear_proxy(self):
        """
        Clear the applied proxy (=> use no proxy at all) in all contexts.
        """
        extension = await self.mv3_extension
        await extension.eval_async("""
            await chrome.proxy.settings.set(
              {value: {mode: "direct"}, scope: 'regular'}
            );
        """, unique_context=False)

    async def _ensure_auth_interception(self, timeout: float = 0.3, set_flag: bool = True):
        # internal, to re-apply auth interception which is broken when a new context gets opened. Due to how extensions in incognito work
        if not self._auth_interception_enabled:
            script = """
                        if(globalThis.authCreds == undefined){globalThis.authCreds = {}}
                        globalThis.onAuth = function onAuth(details) {
                            return globalThis.authCreds[details.challenger.host+":"+details.challenger.port]
                        }
                        chrome.webRequest.onAuthRequired.addListener(
                            onAuth,
                            {urls: ["<all_urls>"]},
                            ['blocking']
                            );
                        """
            mv3_target = await self.mv3_extension
            await mv3_target.execute_script(script, timeout=timeout, unique_context=False)
            if set_flag:
                self._auth_interception_enabled = True

    async def set_auth(self, username: str, password: str, host_with_port):
        """
        Set authentication dynamically to be applied in all contexts.

        .. code-block:: python

            driver.set_auth("user1","passwrd1", "example.com:5001")

        .. warning::

            - Only supported when Chrome has been started with driverless or the extension at ``selenium_driverless/files/mv3_extension`` has been loaded into the browser.

            - ``Socks5`` doesn't support authentication due to `crbug#1309413 <https://bugs.chromium.org/p/chromium/issues/detail?id=1309413>`__.

        :param username:
        :param password:
        :param host_with_port: in format "example.com:5001"

        """
        # provide auth
        await self._ensure_auth_interception()
        mv3_target = await self.mv3_extension
        arg = {
            "authCredentials": {
                "username": username,
                "password": password
            }
        }
        await mv3_target.execute_script("globalThis.authCreds[arguments[1]] = arguments[0]", arg, host_with_port,
                                        unique_context=False)
        self._auth[host_with_port] = arg

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
        return await self.current_context.execute_cdp_cmd(cmd=cmd, cmd_args=cmd_args, timeout=timeout)

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

        :param sink_name: Name of the sink to use as the target.
        """
        return await self.current_target.set_sink_to_use(sink_name=sink_name)

    async def start_desktop_mirroring(self, sink_name: str) -> dict:
        """Starts a desktop mirroring session on a specific receiver target.

        :param sink_name: Name of the sink to use as the target.
        """
        return await self.current_target.start_desktop_mirroring(sink_name=sink_name)

    async def start_tab_mirroring(self, sink_name: str) -> dict:
        """Starts a tab mirroring session on a specific receiver target.

        :param sink_name: Name of the sink to use as the target.
        """
        return await self.current_target.start_tab_mirroring(sink_name=sink_name)

    async def stop_casting(self, sink_name: str) -> dict:
        """Stops the existing Cast session on a specific receiver target.

        :Args:
         - sink_name: Name of the sink to stop the Cast session.
        """
        return await self.current_target.stop_casting(sink_name=sink_name)
