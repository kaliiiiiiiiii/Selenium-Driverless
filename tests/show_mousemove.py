from selenium_driverless import webdriver
from selenium_driverless.utils.utils import read
from selenium_driverless.types.by import By
import asyncio
import aiodebug.log_slow_callbacks

aiodebug.log_slow_callbacks.enable(0.05)


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get("about:blank")
        await driver.execute_script(script=await read("/files/js/show_mousemove.js", sel_root=True))
        elem = await driver.find_element(By.ID, "clear")
        pointer = driver.current_pointer

        move_kwargs = {"total_time": 0.7, "accel": 2, "smooth_soft": 20}
        await driver.current_target.activate()

        for _ in range(50):
            await pointer.click(100, 500, move_kwargs=move_kwargs, move_to=True)
            await asyncio.sleep(0)
            await pointer.click(500, 50, move_kwargs=move_kwargs, move_to=True)
            await asyncio.sleep(0)
        input("Press ENTER to exit")


asyncio.run(main())
