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
        iframe = None
        while not iframe:
            targets = await driver.targets
            for target in list(targets.values()):
                if target.type == "iframe":
                    if target.url[:93] == 'https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/g/turnstile/if/ov2/av0/rcv0/0/':
                        target = await target.Target

                        # ensure we've got the correct iframe
                        text = None
                        try:
                            elem = await target.find_element(By.CSS_SELECTOR, "body > div")
                            text = await elem.text
                        except NoSuchElementException:
                            pass
                        finally:
                            if text:  # 'Only a rest.' text
                                iframe = target
                                break

        await asyncio.sleep(0.5)

        # some random mouse-movements over iframe
        pointer = await driver.current_pointer
        await pointer.move_to(500, 200, smooth_soft=60, total_time=1)
        await pointer.move_to(20, 50, smooth_soft=60, total_time=1)
        await pointer.move_to(8, 45, smooth_soft=60, total_time=1)
        await asyncio.sleep(1)
        await pointer.move_to(500, 200, smooth_soft=60, total_time=1)

        # switch and click on checkbox
        target = iframe
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
