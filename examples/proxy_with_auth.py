from selenium_driverless import webdriver
import asyncio


async def main():
    # socks5 with credentials not supported due to https://bugs.chromium.org/p/chromium/issues/detail?id=1309413
    proxy = "http://user1:passwrd1@example.proxy.com:5001/"

    options = webdriver.ChromeOptions()
    # options.single_proxy = proxy

    async with webdriver.Chrome(options=options) as driver:

        # this will overwrite the proxy for ALL CONTEXTS
        await driver.set_single_proxy(proxy)

        await driver.get("https://browserleaks.com/webrtc")
        await driver.clear_proxy()  # clear proxy
        print()


asyncio.run(main())
