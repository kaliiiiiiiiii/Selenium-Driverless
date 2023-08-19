import unittest

from selenium_driverless import webdriver
from selenium_driverless.types.by import By

import asyncio

driver: webdriver.Chrome = None
loop = asyncio.get_event_loop()


async def make_driver():
    global driver
    driver = await webdriver.Chrome()
    return driver


async def nowsecure():
    global driver
    await driver.get("https://nowsecure.nl#relax")
    await driver.wait_for_cdp("Page.domContentEventFired")
    await asyncio.sleep(0.5)
    elem = await driver.find_element(By.XPATH, "/html/body/div[2]/div/main/p[2]/a")


async def bet365():
    global driver
    await driver.get('https://www.365365824.com/#/IP/B16', wait_load=True)
    await driver.wait_for_cdp("Page.frameStoppedLoading", timeout=15)
    await asyncio.sleep(2)
    login_button = await driver.find_element(By.XPATH, value='//div[contains(@class, "ovm-ParticipantOddsOnly")]')
    await login_button.click()


async def selenium_detector():
    await driver.get('https://hmaker.github.io/selenium-detector/')
    elem = await driver.find_element(By.CSS_SELECTOR, "#chromedriver-token")
    sr = await elem.source
    await elem.write(await driver.execute_script('return window.token'))
    elem2 = await driver.find_element(By.CSS_SELECTOR, "#chromedriver-asynctoken")
    async_token = await driver.execute_async_script('window.getAsyncToken().then(arguments[0])')
    await elem2.write(async_token)
    elem3 = await driver.find_element(By.CSS_SELECTOR, "#chromedriver-test")
    await elem3.click()
    passed = await driver.find_element(By.XPATH, '//*[@id="chromedriver-test-container"]/span')
    text = await passed.text
    assert text == "Passed!"


async def prompt():
    global driver
    global loop
    handles = await driver.window_handles
    target = await driver.switch_to.target(handles[0])

    await driver.get("chrome://version")
    keys = "Hello!"
    script = loop.create_task(driver.execute_script("return prompt('hello?')", timeout=100))
    alert = await driver.switch_to.alert
    await alert.send_keys(keys)
    res = await script
    assert res == keys


class Driver(unittest.TestCase):
    def test_all(self):
        global loop
        loop.run_until_complete(self._test_all())
        self.assertEqual(True, True)

    async def _test_all(self):
        global driver
        await make_driver()

        await prompt()
        await nowsecure()
        await bet365()
        await selenium_detector()

        await driver.quit()


if __name__ == '__main__':
    unittest.TestCase("test_all")
