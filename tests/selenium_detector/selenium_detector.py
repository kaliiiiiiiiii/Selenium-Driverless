from selenium_driverless import webdriver
from selenium_driverless.types.by import By
import asyncio


async def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    async with webdriver.Chrome(options=options) as driver:
        await driver.get('https://hmaker.github.io/selenium-detector/')
        elem = await driver.find_element(By.CSS_SELECTOR, "#chromedriver-token")
        await elem.send_keys(await driver.execute_script('return window.token'))
        elem2 = await driver.find_element(By.CSS_SELECTOR, "#chromedriver-asynctoken")
        async_token = await driver.eval_async('return await window.getAsyncToken()')
        await elem2.send_keys(async_token)
        elem3 = await driver.find_element(By.CSS_SELECTOR, "#chromedriver-test")
        await elem3.click()
        passed = await driver.find_element(By.XPATH, '//*[@id="chromedriver-test-container"]/span')
        text = await passed.text
        assert text == "Passed!"
        print(text)


asyncio.run(main())
