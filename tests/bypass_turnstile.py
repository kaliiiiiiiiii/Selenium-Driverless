from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException
import asyncio


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get("https://nopecha.com/demo/turnstile")

        # wait for iframe and switch to
        page = driver.current_window_handle
        iframes = []
        while len(iframes) != 2:
            targets = await driver.targets
            for target in list(targets.values()):
                if target.type == "iframe":
                    if target.url[:93] == 'https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/if/ov2/av0/rcv0/0/':
                        frame = await target.Target.base_frame
                        info = await target.Target.info
                        iframes.append(target)

        await asyncio.sleep(0.5)

        # some random mouse-movements over iframe
        pointer = await driver.current_pointer
        await pointer.move_to(500, 200, smooth_soft=60, total_time=1)
        await pointer.move_to(20, 50, smooth_soft=60, total_time=1)
        await pointer.move_to(8, 45, smooth_soft=60, total_time=1)
        await asyncio.sleep(1)
        await pointer.move_to(500, 200, smooth_soft=60, total_time=1)

        # switch and click on checkbox
        target = iframes[0].Target
        while True:
            # noinspection PyProtectedMember
            elem = await target._document_elem
            await elem.highlight()
            try:
                checkbox = await target.find_element(By.CSS_SELECTOR, "#challenge-stage > div > label > map > img")
                break
            except NoSuchElementException:
                pass

        await checkbox.click(move_to=True)
        await driver.switch_to.window(page, activate=True)
        input("press ENTER to exit")


asyncio.run(main())
