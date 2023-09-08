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

"""The Alert implementation."""
import asyncio
import warnings


# noinspection PyProtectedMember
class Alert:
    """Allows to work with alerts.

    Use this class to interact with alert prompts.  It contains methods for dismissing,
    accepting, inputting, and getting text from alert prompts.

    Accepting / Dismissing alert prompts::

        Alert(target).accept()
        Alert(target).dismiss()

    Inputting a value into an alert prompt::

        name_prompt = Alert(target)
        name_prompt.send_keys("Willian Shakesphere")
        name_prompt.accept()


    Reading the text of a prompt for verification::

        alert_text = Alert(target).text
        self.assertEqual("Do you wish to quit?", alert_text)
    """

    def __init__(self, target, timeout: float = 5) -> None:
        """Creates a new Alert.

        :Args:
         - target: The WebDriver instance which performs user actions.
        """
        from selenium_driverless.types.target import Target
        self.target: Target = target
        self._timeout = timeout
        self._started = False

    def __await__(self):
        return self._init().__await__()

    async def _init(self):
        if not self._started:
            if not self.target._alert:
                try:
                    await self.target.wait_for_cdp("Page.javascriptDialogOpening", self._timeout)
                except asyncio.TimeoutError:
                    self._warn_not_detected()
            self._started = True
        return self

    def _warn_not_detected(self):
        warnings.warn("clouldn't detect if dialog is shown, you might execute Page.enable before")

    @property
    def text(self) -> str:
        """Gets the text of the Alert."""
        if self.target._alert:
            return self.target._alert["message"]
        self._warn_not_detected()

    @property
    def url(self) -> str:
        if self.target._alert:
            return self.target._alert["url"]
        self._warn_not_detected()

    @property
    def type(self) -> str:
        if self.target._alert:
            return self.target._alert["type"]
        self._warn_not_detected()

    @property
    def has_browser_handler(self) -> bool:
        if self.target._alert:
            return self.target._alert["hasBrowserHandler"]
        self._warn_not_detected()

    @property
    def default_prompt(self):
        if self.target._alert:
            return self.target._alert["defaultPrompt"]
        self._warn_not_detected()

    async def dismiss(self) -> None:
        """Dismisses the alert available."""
        await self.target.execute_cdp_cmd("Page.handleJavaScriptDialog", {"accept": False})

    async def accept(self) -> None:
        """Accepts the alert available."""
        await self.target.execute_cdp_cmd("Page.handleJavaScriptDialog", {"accept": True})

    # noinspection PyPep8Naming
    async def send_keys(self, keysToSend: str) -> None:
        """Send Keys to the Alert.

        :Args:
         - keysToSend: The text to be sent to Alert.
        """
        await self.target.execute_cdp_cmd("Page.handleJavaScriptDialog", {"accept": True, "promptText": keysToSend})
