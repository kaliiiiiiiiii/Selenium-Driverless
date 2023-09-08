import websockets
import traceback
import asyncio

from selenium_driverless import webdriver

global driver


async def attached_callback(data):
    global driver
    # noinspection PyBroadException,PyUnresolvedReferences
    try:
        target = await driver.get_target(data["targetInfo"]["targetId"])
        print(data["targetInfo"]["url"])
        if data['waitingForDebugger']:
            await target.execute_cdp_cmd("Runtime.runIfWaitingForDebugger", timeout=2)
    except websockets.exceptions.InvalidMessage:
        # closed
        pass
    except Exception:
        traceback.print_exc()


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
