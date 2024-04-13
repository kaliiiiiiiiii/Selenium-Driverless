import asyncio
from selenium_driverless import webdriver
import sys
import aiodebug.log_slow_callbacks

aiodebug.log_slow_callbacks.enable(0.05)

global driver

handler = (lambda e: print(f'Exception in event-handler:\n{e.__class__.__module__}.{e.__class__.__name__}: {e}',
                           file=sys.stderr))
sys.modules["selenium_driverless"].EXC_HANDLER = handler
sys.modules["cdp_socket"].EXC_HANDLER = handler


async def attached_callback(data):
    global driver
    target = await driver.get_target(data["targetInfo"]["targetId"])
    print(data["targetInfo"]["url"])
    if data['waitingForDebugger']:
        await target.execute_cdp_cmd("Runtime.runIfWaitingForDebugger", timeout=2)
    raise Exception("testException")


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
        a = True
        while a:
            await asyncio.sleep(2)


asyncio.run(main())
