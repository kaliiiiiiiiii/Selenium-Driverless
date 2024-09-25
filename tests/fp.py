import json

from selenium_driverless import webdriver
import asyncio
import os
import pathlib
import jsondiff
import pprint

with open(pathlib.Path(os.getcwd() + "/assets/clean.json"), "r", encoding="utf-8") as f:
    clean = json.load(f)


async def get_fp(driver: webdriver.Chrome):
    await driver.get(os.getcwd() + "/assets/index.html")
    js = """
        var elem = document.documentElement;
        function callback(e){
            window.fp_click_callback(e)
            elem.removeEventListener("mousedown", this);
        }
        var data = getFingerprint(true, false);
        elem.addEventListener("mousedown", callback);
        return JSON.stringify(await data)
    """
    await asyncio.sleep(1)
    fut = asyncio.ensure_future(driver.eval_async(js, timeout=10, unique_context=False))
    await asyncio.sleep(1)
    pointer = driver.current_pointer
    await pointer.down(x=10, y=10)
    fp = json.loads(await fut)
    return fp


def clean_passthrough(fp: dict):
    # network speed can be different
    del fp["connection"]

    # window size can be different
    del fp['innerHeight']
    del fp['innerWidth']
    del fp['outerHeight']
    del fp['outerWidth']

    del fp["is_bot"]

    return fp


async def base_driver():
    options = webdriver.ChromeOptions()
    env = os.environ.copy()
    options.env = env
    env['NUMBER_OF_PROCESSORS'] = "4"
    async with webdriver.Chrome(options=options) as driver:
        return await get_fp(driver)


async def main():
    global clean
    default, = await asyncio.gather(
        base_driver()
    )
    clean = clean_passthrough(clean)
    default = clean_passthrough(default)
    default_diff = jsondiff.diff(default, clean)
    pprint.pprint(default_diff)


asyncio.run(main())
