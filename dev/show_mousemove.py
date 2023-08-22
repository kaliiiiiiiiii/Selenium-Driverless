from selenium_driverless import webdriver
from selenium_driverless.utils.utils import read
from selenium_driverless.types.by import By
from selenium_driverless.input.pointer import Pointer
import asyncio
import os


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get("about:blank", wait_load=False)
        await driver.execute_script(script=read(os.getcwd()+"/show_mousemove.js", sel_root=False))
        clear = await driver.find_element(By.ID, "clear")
        p = Pointer(driver=driver)
        await p.move_to(x=100, y=100)
        await p.move_to(x=100, y=105)
        await p.move_to(x=100, y=110)
        await clear.click()
        print(3)

asyncio.run(main())

