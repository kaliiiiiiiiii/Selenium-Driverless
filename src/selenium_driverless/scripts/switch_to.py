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

import asyncio
from typing import Optional
from typing import Union


from selenium_driverless.types.by import By
from selenium_driverless.types.alert import Alert
from selenium_driverless.types.target import TargetInfo, Target

from selenium_driverless.types.target import NoSuchIframe
from selenium_driverless.types.webelement import WebElement, NoSuchElementException


class SwitchTo:
    def __init__(self, context, context_id: str = None, loop: asyncio.AbstractEventLoop = None) -> None:
        from selenium_driverless.types.context import Context
        self._context: Context = context
        self._alert = None
        self._started = False
        self._context_id = context_id
        self._loop = loop
        # noinspection PyProtectedMember
        self._is_incognito = self._context._is_incognito

    def __await__(self):
        return self._init().__await__()

    async def _init(self):
        if not self._started:
            self._started = True
        return self

    @property
    def active_element(self) -> WebElement:
        """Returns the element with focus, or BODY if nothing has focus.

        :Usage:
            ::

                element = target.switch_to.active_element
        """
        raise NotImplementedError()

    @property
    async def alert(self) -> Alert:
        """Switches focus to an alert on the page.

        :Usage:
            ::

                alert = target.switch_to.alert
        """
        return await self.get_alert()

    async def get_alert(self, target_id: str = None, timeout: float = 5) -> Alert:
        """Switches focus to an alert on the page.

        :Usage:
            ::

                alert = target.switch_to.alert
        """
        target = await self._context.get_target(target_id=target_id)
        return await target.get_alert(timeout=timeout)

    async def default_content(self, activate: bool = False) -> Target:
        """Switch focus to the default frame.

        :Usage:
            ::

                target.switch_to.default_content()
        """
        base_target = self._context.current_target.base_target
        if base_target:
            return await self.target(target_id=base_target, activate=activate)

    async def frame(self, frame_reference: Union[str, int, WebElement], activate: bool = False) -> None:
        """Switches focus to the specified frame, by index, name, or
        webelement.

        :Args:
         - frame_reference: The name of the window to switch to, an integer representing the index,
                            or a webelement that is an (i)frame to switch to.

        :Usage:
            ::

                target.switch_to.frame('frame_name')
                target.switch_to.frame(1)
                target.switch_to.frame(target.find_elements(By.TAG_NAME, "iframe")[0])
        """
        if isinstance(frame_reference, str):
            try:
                frame_reference = await self._context.find_element(By.ID, frame_reference)
            except NoSuchElementException:
                try:
                    frame_reference = await self._context.find_element(By.NAME, frame_reference)
                except NoSuchElementException:
                    raise NoSuchIframe(frame_reference, f"couldn't get element by: {frame_reference}")
        target = await self._context.current_target.get_target_for_iframe(frame_reference)
        if activate:
            await target.focus()
        return target

    async def target(self, target_id: str or TargetInfo or WebElement, activate: bool = True) -> Target:
        if isinstance(target_id, TargetInfo):
            self._context._current_target = target_id.Target
        elif isinstance(target_id, Target):
            self._context._current_target = target_id
        elif isinstance(target_id, WebElement):
            self._context._current_target = self.frame(target_id, activate=False)
        else:
            self._context._current_target = await self._context.get_target(target_id)

        if activate:
            await self._context.current_target.focus()
        return self._context.current_target

    async def new_window(self, type_hint: Optional[str] = "tab", url="", activate: bool = True) -> Target:
        """Switches to a new top-level browsing context.

        The type hint can be one of "tab" or "window". If not specified the
        browser will automatically select it.

        :Usage:
            ::

                target.switch_to.new_window('tab')
        """
        if self._is_incognito and url in ["chrome://extensions"]:
            raise ValueError(f"{url} only supported in non-incognito contexts")
        new_tab = False
        if type_hint == "window":
            new_tab = True
        elif type_hint == "tab":
            pass
        else:
            raise ValueError("type hint needs to be 'window' or 'tab'")
        args = {"url": url, "newWindow": new_tab, "forTab": new_tab}
        # noinspection PyProtectedMember
        if self._context_id and self._is_incognito:
            args["browserContextId"] = self._context_id
        target = await self._context.base_target.execute_cdp_cmd("Target.createTarget", args)
        target_id = target["targetId"]
        return await self.target(target_id, activate=activate)

    async def parent_frame(self, activate: bool = False) -> None:
        """Switches focus to the parent context. If the current context is the
        top level browsing context, the context remains unchanged.

        :Usage:
            ::

                target.switch_to.parent_frame()
        """
        # noinspection PyProtectedMember
        parent = self._context.current_target._parent_target
        if parent:
            await self.target(target_id=parent, activate=activate)

    async def window(self, window_id: str or TargetInfo, activate: bool = True) -> None:
        """Switches focus to the specified window.

        :Args:
         - window_name: The name or window handle of the window to switch to.

        :Usage:
            ::

                target.switch_to.window('main')
        """
        await self.target(window_id, activate=activate)
