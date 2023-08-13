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

from selenium.webdriver.remote.command import Command


# noinspection PyProtectedMember
class Alert:
    """Allows to work with alerts.

    Use this class to interact with alert prompts.  It contains methods for dismissing,
    accepting, inputting, and getting text from alert prompts.

    Accepting / Dismissing alert prompts::

        Alert(driver).accept()
        Alert(driver).dismiss()

    Inputting a value into an alert prompt::

        name_prompt = Alert(driver)
        name_prompt.send_keys("Willian Shakesphere")
        name_prompt.accept()


    Reading the text of a prompt for verification::

        alert_text = Alert(driver).text
        self.assertEqual("Do you wish to quit?", alert_text)
    """

    def __init__(self, driver) -> None:
        """Creates a new Alert.

        :Args:
         - driver: The WebDriver instance which performs user actions.
        """
        from selenium_driverless.scripts.switch_to import SwitchTo
        from selenium_driverless.webdriver import Chrome
        self.driver: Chrome = driver
        self.switch_to: SwitchTo = driver.switch_to

    def __await__(self):
        return self._init().__await__()

    async def _init(self):
        if not self.switch_to._alert:
            try:
                await self.driver.wait_for_cdp("Page.javascriptDialogOpening", 10)
            except asyncio.TimeoutError:
                self._warn_not_detected()
        return self

    def _warn_not_detected(self):
        warnings.warn("clouldn't detect if dialog is shown, you might execute Page.enable before")

    @property
    def text(self) -> str:
        """Gets the text of the Alert."""
        if self.switch_to._alert:
            return self.switch_to._alert["message"]
        self._warn_not_detected()

    @property
    def url(self) -> str:
        if self.switch_to._alert:
            return self.switch_to._alert["url"]
        self._warn_not_detected()

    @property
    def type(self) -> str:
        if self.switch_to._alert:
            return self.switch_to._alert["type"]
        self._warn_not_detected()

    @property
    def has_browser_handler(self) -> bool:
        if self.switch_to._alert:
            return self.switch_to._alert["hasBrowserHandler"]
        self._warn_not_detected()

    @property
    def default_prompt(self):
        if self.switch_to._alert:
            return self.switch_to._alert["defaultPrompt"]
        self._warn_not_detected()

    async def dismiss(self) -> None:
        """Dismisses the alert available."""
        await self.driver.execute_cdp_cmd("Page.handleJavaScriptDialog", {"accept": False})

    async def accept(self) -> None:
        """Accepts the alert available.

        :Usage:
            ::

                Alert(driver).accept() # Confirm a alert dialog.
        """
        await self.driver.execute_cdp_cmd("Page.handleJavaScriptDialog", {"accept": True})

    # noinspection PyPep8Naming
    async def send_keys(self, keysToSend: str) -> None:
        """Send Keys to the Alert.

        :Args:
         - keysToSend: The text to be sent to Alert.
        """
        await self.driver.execute_cdp_cmd("Page.handleJavaScriptDialog", {"accept": True, "promptText": keysToSend})
