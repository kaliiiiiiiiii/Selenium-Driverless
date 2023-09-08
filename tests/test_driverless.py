import unittest

from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException

import asyncio

loop = asyncio.get_event_loop()


async def make_driver():
    return await webdriver.Chrome()


async def nowsecure(driver):
    async def get_elem():
        return await driver.find_element(By.XPATH, "/html/body/div[2]/div/main/p[2]/a")

    await driver.get("https://nowsecure.nl#relax", wait_load=True)
    await asyncio.sleep(0.5)
    try:
        await get_elem()
    except NoSuchElementException:
        await driver.wait_for_cdp("Page.domContentEventFired")
    await get_elem()


async def unique_execution_context(driver):
    await driver.get('chrome://version')
    script = """
            const proxy = new Proxy(document.documentElement, {
              get(target, prop, receiver) {
                if(prop === "outerHTML"){
                    console.log('detected access on "'+prop+'"', receiver)
                    return "mocked value:)"
                }
                else{return Reflect.get(...arguments)}
              },
            });
            Object.defineProperty(document, "documentElement", {
              value: proxy
            })
            """
    await driver.execute_script(script)
    src = await driver.execute_script("return document.documentElement.outerHTML", unique_context=True)
    mocked = await driver.execute_script("return document.documentElement.outerHTML", unique_context=False)
    assert mocked == "mocked value:)"
    assert src != "mocked value:)"


async def bet365(driver):
    async def click_login():
        login_button = await driver.find_element(By.XPATH, value='//div[contains(@class, "ovm-ParticipantOddsOnly")]')
        await login_button.click()

    await driver.get('https://www.365365824.com/#/IP/B16', wait_load=True)
    await asyncio.sleep(0.5)
    try:
        await click_login()
    except NoSuchElementException:
        await driver.wait_for_cdp("Page.frameStoppedLoading", timeout=15)
        await asyncio.sleep(2)
        await click_login()


async def selenium_detector(driver):
    await driver.get('https://hmaker.github.io/selenium-detector/')
    elem = await driver.find_element(By.CSS_SELECTOR, "#chromedriver-token")
    await elem.write(await driver.execute_script('return window.token'))
    elem2 = await driver.find_element(By.CSS_SELECTOR, "#chromedriver-asynctoken")
    async_token = await driver.execute_async_script('window.getAsyncToken().then(arguments[0])')
    await elem2.write(async_token)
    elem3 = await driver.find_element(By.CSS_SELECTOR, "#chromedriver-test")
    await elem3.click()
    passed = await driver.find_element(By.XPATH, '//*[@id="chromedriver-test-container"]/span')
    text = await passed.text
    assert text == "Passed!"


async def prompt(driver):
    await driver.get("chrome://version")
    keys = "Hello!"
    script = asyncio.create_task(driver.execute_script("return prompt('hello?')", timeout=100))
    await asyncio.sleep(0.5)
    alert = await driver.get_alert(timeout=5)
    await alert.send_keys(keys)
    res = await script
    assert res == keys


async def create_tabs(n_tabs: int, driver):
    targets = [driver.current_target]
    for _ in range(n_tabs - 1):
        targets.append(await driver.switch_to.new_window("tab"))
    return targets


class Driver(unittest.TestCase):
    def test_all(self):
        global loop
        loop.run_until_complete(self._test_all())
        self.assertEqual(True, True)

    async def _test_all(self):
        tests = [
            prompt,
            unique_execution_context,
            nowsecure,
            bet365,
            selenium_detector
        ]

        driver = await make_driver()
        tabs = await create_tabs(len(tests), driver)

        coros = []
        for test, target in zip(tests, tabs):
            coros.append(test(target))

        await asyncio.gather(*coros)
        await driver.quit()


if __name__ == '__main__':
    unittest.TestCase("test_all")
