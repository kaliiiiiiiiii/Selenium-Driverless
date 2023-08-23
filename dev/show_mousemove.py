from selenium_driverless import webdriver
from selenium_driverless.utils.utils import read
from selenium_driverless.types.by import By
from selenium_driverless.input.pointer import Pointer
import asyncio
import os
import time


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get("about:blank")
        p = Pointer(driver=driver)
        await driver.execute_script(script=read(os.getcwd() + "/show_mousemove.js", sel_root=False))
        clear = await driver.find_element(By.ID, "clear")

        i = -1
        for y in range(50, 501, 1):
            await p.move_to(x=100, y=y)
            if i == -1:
                start = time.monotonic() + 0.017  # aproximately,
            i += 1
        stop = time.monotonic()
        d_time = stop - start
        events_per_sec = i / d_time
        await clear.click()
        print(events_per_sec)


asyncio.run(main())
