from selenium_driverless import webdriver
import asyncio
global driver


async def attached_callback(data):
    global driver
    target = await driver.get_target(data["targetInfo"]["targetId"])
    print(data["targetInfo"]["url"])
    if data['waitingForDebugger']:
        await target.execute_cdp_cmd("Runtime.runIfWaitingForDebugger", timeout=2)


async def main():
    global driver
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.base_target.execute_cdp_cmd("Target.setDiscoverTargets", {"discover": True})
        await driver.base_target.execute_cdp_cmd("Target.setAutoAttach",
                                                 {"autoAttach": True, "waitForDebuggerOnStart": True, "flatten": True})
        await driver.base_target.add_cdp_listener("Target.attachedToTarget", attached_callback)
        await driver.base_target.add_cdp_listener("Target.targetDestroyed", print)
        url = "https://abrahamjuliot.github.io/creepjs/tests/workers.html"
        await driver.get(url)
        await driver.switch_to.new_window(url=url)
        input("press ENTER to exit: ")


asyncio.run(main())
