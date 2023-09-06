from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException
import asyncio


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get("https://nopecha.com/demo/turnstile")
        await asyncio.sleep(0.5)

        # some random mouse-movements over iframes
        pointer = await driver.current_pointer
        await pointer.move_to(500, 200, smooth_soft=60, total_time=0.5)
        await pointer.move_to(20, 50, smooth_soft=60, total_time=0.5)
        await pointer.move_to(8, 45, smooth_soft=60, total_time=0.5)
        await pointer.move_to(500, 200, smooth_soft=60, total_time=0.5)
        await pointer.move_to(166, 206, smooth_soft=60, total_time=0.5)
        await pointer.move_to(200, 205, smooth_soft=60, total_time=0.5)

        iframes = await driver.find_elements(By.TAG_NAME, "iframe")
        await asyncio.sleep(0.5)
        targets = [await driver.get_target_for_iframe(iframes[0]), await driver.get_target_for_iframe(iframes[1])]
        for target in targets:
            # filter out correct iframe target
            text = None
            try:
                elem = await target.find_element(By.CSS_SELECTOR, "body > div")
                text = await elem.text
            except NoSuchElementException:
                pass
            finally:
                if text:  # 'Only a test.' text
                    break

        while True:
            # wait for checkbox loaded
            try:
                checkbox = await target.find_element(By.CSS_SELECTOR, "#challenge-stage > div > label > map > img")
                break
            except NoSuchElementException:
                await asyncio.sleep(0.1)

        await checkbox.click(move_to=True)
        input("press ENTER to exit")


asyncio.run(main())
