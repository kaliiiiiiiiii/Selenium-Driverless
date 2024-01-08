from selenium_driverless import webdriver
import asyncio


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get('https://reddit.com', wait_load=True)
        pointer = await driver.current_pointer
        debug_script = """
                document.addEventListener("wheel", console.log);
                """
        await driver.execute_script(debug_script)
        await asyncio.sleep(2)
        for i in range(100):
            await pointer.scroll(delta_y=100)
            print("scrolled")
            await asyncio.sleep(0.5)
        await asyncio.sleep(1000)

asyncio.run(main())
