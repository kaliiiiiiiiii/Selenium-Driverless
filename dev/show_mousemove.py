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
        await driver.get("about:blank", wait_load=False)
        await driver.execute_script(script=read(os.getcwd() + "/show_mousemove.js", sel_root=False))
        clear = await driver.find_element(By.ID, "clear")
        p = Pointer(driver=driver)
        start = time.process_time()
        for y in range(100, 400, 1):
            await p.move_to(x=100, y=y)
            await p.move_to(x=100, y=y)
            await p.move_to(x=100, y=y)
        stop = time.process_time()
        d_time = stop - start
        events_per_sec = 300/d_time
        await clear.click()


asyncio.run(main())
