from selenium_driverless import webdriver
import asyncio


async def main():
    proxy = "http://user1:passwrd1@example.proxy.com:5001/"

    options = webdriver.ChromeOptions()
    options.single_proxy = proxy
    async with webdriver.Chrome(options=options) as driver:
        # or set dynamically
        # await driver.set_single_proxy(proxy)
        await driver.get("https://browserleaks.com/webrtc")
        await driver.clear_proxy() # clear proxy
        print()


asyncio.run(main())
