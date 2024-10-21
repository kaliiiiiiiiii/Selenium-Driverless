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

import asyncio
import typing
from typing import Union
import warnings


from selenium_driverless.types.by import By
from selenium_driverless.types.alert import Alert
from selenium_driverless.types.target import TargetInfo, Target

from selenium_driverless.types.target import NoSuchIframe
from selenium_driverless.types.webelement import WebElement, NoSuchElementException


class SwitchTo:
    """
    the SwitchTo class

    .. warning::
        except for switching to targets, do not use this class
    """
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
    async def alert(self) -> Alert:
        """Switches focus to an alert on the page.

        :Usage:
            ::

                alert = target.switch_to.alert
        """
        return await self.get_alert()

    async def get_alert(self, timeout: float = 5) -> Alert:
        """Switches focus to an alert on the page.

        :Usage:
            ::

                alert = target.switch_to.alert
        """
        return await self._context.current_target.get_alert(timeout=timeout)

    async def default_content(self, activate: bool = False) -> Target:
        """Switch focus to the default frame.

        :Usage:
            ::

                target.switch_to.default_content()
        """
        base_target = self._context.current_target.base_target
        if base_target:
            return await self.target(target_id=base_target, activate=activate)

    async def frame(self, frame_reference: Union[str, int, WebElement], focus:bool=True) -> None:
        """Switches to the specified frame

        :param frame_reference: the reference by ID, name, index, or WebElement
        :param focus: whether to emulate focus on the frame
        :param focus: whether to emulate focus on the iframe
        """
        warnings.warn(
            "driver.switch_to.iframe deprecated and not reliable use Webelement.content_document instead",
            DeprecationWarning)
        if isinstance(frame_reference, str):
            try:
                frame_reference = await self._context.find_element(By.ID, frame_reference)
            except NoSuchElementException:
                try:
                    frame_reference = await self._context.find_element(By.NAME, frame_reference)
                except NoSuchElementException:
                    pass
        if isinstance(frame_reference, int):
            try:
                frames = await self._context.find_elements(By.TAG_NAME, "iframe")
                frame_reference = frames[frame_reference]
            except KeyError:
                pass

        if not isinstance(frame_reference, WebElement):
            raise NoSuchIframe(frame_reference, f"couldn't get element by: {frame_reference}")
        target = await self._context.current_target.get_target_for_iframe(frame_reference)
        if focus:
            await target.focus()
        await self.target(target)
        return target

    async def target(self, target_id: typing.Union[str, TargetInfo, Target], activate: bool = False, focus:bool=True) -> Target:
        """
        switches to a target

        :param target_id: the target to switch to
        :param activate: whether to bring the target to the front
        :param focus: whether to emulate focus on the target
        """
        if isinstance(target_id, TargetInfo):
            self._context._current_target = target_id.Target
        elif isinstance(target_id, Target):
            self._context._current_target = target_id
        elif isinstance(target_id, WebElement):
            # noinspection PyDeprecation
            self._context._current_target = self.frame(target_id)
        else:
            self._context._current_target = await self._context.get_target(target_id)

        if activate:
            await self._context.current_target.activate()
        if focus:
            await self._context.current_target.focus()
        return self._context.current_target

    async def window(self, window_id: str or TargetInfo, activate: bool = False, focus:bool=True) -> Target:
        """
        switches to a window

        alias to :func:`SwitchTo.target <selenium_driverless.scripts.switch_to.SwitchTo.target`
        """
        return await self.target(window_id, activate=activate, focus=focus)

    async def new_window(self, type_hint: typing.Literal["tab", "window"] = "tab", url="", activate: bool = False,
                         focus: bool = True, background: bool = True) -> Target:
        """creates a new tab or window

        :param type_hint: what kind of target to create
        :param url: url to start the target at
        :param activate: whether to bring the target to the front
        :param focus: whether to emulate focus on the target
        :param background: whether to start the target in the background
        """
        target = await self._context.new_window(type_hint=type_hint, url=url, activate=activate, focus=focus, background=background)
        return await self.target(target)

    async def parent_frame(self, activate: bool = False) -> Target:
        raise NotImplemented()
