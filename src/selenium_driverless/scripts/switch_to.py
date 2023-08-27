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

from typing import Optional
from typing import Union

from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoSuchFrameException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from selenium.webdriver.remote.command import Command

from selenium_driverless.scripts.alert import Alert
from selenium_driverless.sync.alert import Alert as SyncAlert


class SwitchTo:
    def __init__(self, driver) -> None:
        from selenium_driverless.webdriver import Chrome
        self._loop = None
        self._driver: Chrome = driver
        self._alert = None

    def __await__(self):
        return self._init().__await__()

    async def _init(self):
        def set_alert(alert):
            self._alert = alert

        # noinspection PyUnusedLocal
        def remove_alert(alert):
            self._alert = None

        await self._driver.add_cdp_listener("Page.javascriptDialogOpening", set_alert)
        await self._driver.add_cdp_listener("Page.javascriptDialogClosed", remove_alert)
        return self

    @property
    def active_element(self) -> WebElement:
        """Returns the element with focus, or BODY if nothing has focus.

        :Usage:
            ::

                element = driver.switch_to.active_element
        """
        raise NotImplementedError('You might use driver.switch_to.target(driver.targets[0]["targetId"])')

    @property
    async def alert(self) -> Alert:
        """Switches focus to an alert on the page.

        :Usage:
            ::

                alert = driver.switch_to.alert
        """
        if self._loop:
            alert = SyncAlert(self._driver, loop=self._loop)
        else:
            alert = await Alert(self._driver)
        # noinspection PyProtectedMember
        if not self._driver._page_enabled:
            await self._driver.execute_cdp_cmd("Page.enable", disconnect_connect=False)
        return alert

    async def default_content(self) -> None:
        """Switch focus to the default frame.

        :Usage:
            ::

                driver.switch_to.default_content()
        """
        raise NotImplementedError('You might use driver.switch_to.target(driver.targets[0]["targetId"])')

    async def frame(self, frame_reference: Union[str, int, WebElement]) -> None:
        """Switches focus to the specified frame, by index, name, or
        webelement.

        :Args:
         - frame_reference: The name of the window to switch to, an integer representing the index,
                            or a webelement that is an (i)frame to switch to.

        :Usage:
            ::

                driver.switch_to.frame('frame_name')
                driver.switch_to.frame(1)
                driver.switch_to.frame(driver.find_elements(By.TAG_NAME, "iframe")[0])
        """
        if isinstance(frame_reference, str):
            try:
                frame_reference = await self._driver.find_element(By.ID, frame_reference)
            except NoSuchElementException:
                try:
                    frame_reference = await self._driver.find_element(By.NAME, frame_reference)
                except NoSuchElementException:
                    raise NoSuchFrameException(frame_reference)

        raise NotImplementedError('You might use driver.switch_to.target(driver.targets[0]["targetId"])')

    async def target(self, target_id: str, activate: bool = True):
        from cdp_socket.socket import SingleCDPSocket

        socket: SingleCDPSocket = await self._driver.base.get_socket(sock_id=target_id)
        self._driver._current_target = socket.id
        self._driver._global_this_ = None
        self._driver._document_elem_ = None
        if activate:
            await self._driver.execute_cdp_cmd("Target.activateTarget",
                                               {"targetId": self._driver.current_window_handle})
        return target_id

    async def new_window(self, type_hint: Optional[str] = "tab", url="", activate: bool = True) -> None:
        """Switches to a new top-level browsing context.

        The type hint can be one of "tab" or "window". If not specified the
        browser will automatically select it.

        :Usage:
            ::

                driver.switch_to.new_window('tab')
        """
        new_tab = False
        if type_hint == "window":
            new_tab = True
        elif type_hint == "tab":
            pass
        else:
            raise ValueError("type hint needs to be 'window' or 'tab'")
        args = {"url": url, "newWindow": new_tab, "forTab": new_tab}
        target = await self._driver.execute_cdp_cmd("Target.createTarget", args)
        target_id = target["targetId"]
        await self.target(target_id, activate=activate)
        return target_id

    async def parent_frame(self) -> None:
        """Switches focus to the parent context. If the current context is the
        top level browsing context, the context remains unchanged.

        :Usage:
            ::

                driver.switch_to.parent_frame()
        """
        await self._driver.execute(Command.SWITCH_TO_PARENT_FRAME)

    async def window(self, window_name, activate: bool = True) -> None:
        """Switches focus to the specified window.

        :Args:
         - window_name: The name or window handle of the window to switch to.

        :Usage:
            ::

                driver.switch_to.window('main')
        """
        await self.target(window_name, activate=activate)
