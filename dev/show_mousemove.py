from selenium_driverless import webdriver
from selenium_driverless.utils.utils import read
from selenium_driverless.types.by import By
import asyncio
import os


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get("about:blank")
        await driver.execute_script(script=read("/files/js/show_mousemove.js"))
        elem = await driver.find_element(By.ID, "clear")

        move_kwargs = {"total_time": 0.7, "accel": 2, "smooth_soft": 20}

        for _ in range(50):
            await driver.pointer.click(100, 500, move_kwargs=move_kwargs, move_to=True)
            await driver.pointer.click(500, 50, move_kwargs=move_kwargs, move_to=True)
        input("Press ENTER to exit")


asyncio.run(main())
