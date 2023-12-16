import asyncio
import unittest

from selenium_driverless import webdriver
from selenium_driverless.types.by import By

loop = asyncio.get_event_loop()


async def make_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    return await webdriver.Chrome(options, debug=True)


async def nowsecure(driver):
    async def get_elem():
        return await driver.find_element(By.XPATH, "/html/body/div[2]/div/main/p[2]/a")

    await driver.get("https://nowsecure.nl#relax", wait_load=True)
    await asyncio.sleep(0.5)
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
        login_button = await driver.find_element(By.XPATH, value='//div[contains(@class, "ovm-ParticipantOddsOnly")]', timeout=30)
        await login_button.click()

    await driver.focus()
    await driver.get('https://www.365365824.com/#/IP/B16', wait_load=True)
    await asyncio.sleep(1)
    await click_login()


async def selenium_detector(driver):
    await driver.get('https://hmaker.github.io/selenium-detector/')
    await asyncio.sleep(1)
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
    # test contexts
    context = await driver.new_context()

    targets = [driver.current_target, context.current_target]
    for _ in range(n_tabs - 2):
        targets.append(await driver.new_window("tab"))
    return targets


class Driver(unittest.TestCase):
    def test_all(self):
        global loop
        loop.run_until_complete(self._test_all())
        self.assertEqual(True, True)

    @staticmethod
    async def _test_all():
        tests = [
            prompt,
            bet365,
            unique_execution_context,
            nowsecure,
            selenium_detector
        ]
        driver = await make_driver()
        try:
            tabs = await create_tabs(len(tests), driver)

            coros = []
            for test, target in zip(tests, tabs):
                coros.append(test(target))

            await asyncio.gather(*coros)
        except Exception as e:
            await driver.quit()
            raise e
        await driver.quit()


if __name__ == '__main__':
    unittest.TestCase("test_all")
