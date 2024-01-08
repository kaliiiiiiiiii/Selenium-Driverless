import asyncio
import random


class Keyboard:
    def __init__(self, driver, keyboard_type):
        self._driver = driver
        self._keyboard_type = keyboard_type

        # do something to fetch special_keys like (shift, ctrl, alt) for keyboard_type
        # Just using testdata for now
        self.shift_keys = ["!", '"', "#", "¤", "%", "&", "/", "(", ")", "=", "?", "`", "^", "*", "_", ":", ";", ">"]
        self.ctrl_keys = ["[", "]", "{", "}", "\\", "|", "@", "£", "€", "~", "<"]

    async def down(self, key: str):
        await self._driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
            "type": "KeyDown",
            "text": key
        })

    async def up(self, key: str):
        await self._driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
            "type": "KeyUp",
            "text": key
        })

    async def random_timeout(self, timeout):
        return random.uniform(timeout - (timeout*0.5), timeout - (timeout*0.05))

    async def type_char(self, char: str, timeout: float = 0.1):
        await self.down(char)
        await asyncio.sleep(await self.random_timeout(timeout))
        await self.up(char)

    async def type_text(self, text: str, timeout: float = 0.1):
        for char in text:

            special_key = None
            if char in self.shift_keys or char.isupper():
                special_key = "Shift"
            elif char in self.ctrl_keys:
                special_key = "Control"

            if special_key:
                await self._driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
                    "type": "KeyDown",
                    "key": special_key
                })
                await asyncio.sleep(random.randint(50, 100) / 1000)

                await self.type_char(char, timeout)

                await self._driver.execute_cdp_cmd("Input.dispatchKeyEvent", {
                    "type": "KeyUp",
                    "key": special_key
                })
                await asyncio.sleep(random.randint(50, 100) / 1000)
            else:
                await self.type_char(char, timeout)