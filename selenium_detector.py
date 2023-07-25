from selenium_driverless import webdriver
import asyncio


async def main():
    options = webdriver.Options()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get('https://hmaker.github.io/selenium-detector/')
        elem = await driver.execute_script('return document.querySelector("#chromedriver-token")')
        await elem.send_keys(await driver.execute_script('return window.token'))
        elem2 = await driver.execute_script('return document.querySelector("#chromedriver-asynctoken")')
        async_token = await driver.execute_async_script('window.getAsyncToken().then(arguments[0])')
        await elem2.send_keys(async_token)
        elem3 = await driver.execute_script('return document.querySelector("#chromedriver-test")')
        await elem3.click()
        print(await driver.title)


asyncio.run(main())
