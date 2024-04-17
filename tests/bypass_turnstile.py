import asyncio

from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException


async def main():
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless=new")
    async with webdriver.Chrome(options=options) as driver:
        await driver.get("https://nopecha.com/demo/turnstile")
        await asyncio.sleep(0.5)

        # some random mouse-movements over iframes
        pointer = driver.current_pointer
        await pointer.move_to(500, 200, smooth_soft=60, total_time=0.5)
        await pointer.move_to(20, 50, smooth_soft=60, total_time=0.5)
        await pointer.move_to(8, 45, smooth_soft=60, total_time=0.5)
        await pointer.move_to(500, 200, smooth_soft=60, total_time=0.5)
        await pointer.move_to(166, 206, smooth_soft=60, total_time=0.5)
        await pointer.move_to(200, 205, smooth_soft=60, total_time=0.5)

        iframes = await driver.find_elements(By.TAG_NAME, "iframe")
        await asyncio.sleep(0.5)

        iframe_document = None
        for iframe in iframes:
            # filter out correct iframe document
            iframe_document = await iframe.content_document
            try:
                checkbox = await iframe_document.find_element(By.CSS_SELECTOR,
                                                              "#challenge-stage > div > label > input[type=checkbox]",
                                                              timeout=5)
            except NoSuchElementException:
                pass
            else:
                await checkbox.click(move_to=True)
                await asyncio.sleep(1)
        await asyncio.sleep(2)
        print("saving screenshot")
        await driver.save_screenshot("turnstile_captcha.png")


asyncio.run(main())
