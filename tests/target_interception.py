from selenium_driverless.sync import webdriver
from selenium_driverless import webdriver
import asyncio


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        context_1 = driver.current_context
        context_2 = await driver.new_context(proxy_bypass_list=["localhost"], proxy_server="http://localhost:5000")
        await context_1.current_target.get("chrome://net-internals/#proxy")
        await context_2.get("chrome://net-internals/#proxy")
        input("press ENTER to exit:)")


asyncio.run(main())
