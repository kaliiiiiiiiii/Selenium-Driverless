from selenium_driverless import webdriver
import asyncio


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get('https://abrahamjuliot.github.io/creepjs/', wait_load=True)
        print(await driver.title)


asyncio.run(main())