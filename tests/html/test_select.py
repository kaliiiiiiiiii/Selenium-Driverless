import pytest
import asyncio
from selenium_driverless.types.target import Target
from selenium_driverless.webdriver import Chrome
from selenium_driverless.types.by import By
from selenium_driverless.input.utils import select

from cdp_patches.input import AsyncInput

# puppeteer:
# https://github.com/puppeteer/puppeteer/blob/409d244aed480fbb5254f852afb16bd101692f9a/packages/puppeteer-core/src/api/ElementHandle.ts#L919-L961
# selenium:
# https://source.chromium.org/chromium/chromium/src/+/main:third_party/selenium-atoms/atoms.cc;l=706;drc=81d53181af5d6645d8b6ea5cca60c059edae5a3c
# playwright
# https://github.com/microsoft/playwright/blob/1a7d6749daa18cb26c40bc58abb56af9ffe69f02/packages/playwright-core/src/server/injected/injectedScript.ts#L594-L637
# drissionpage
# https://github.com/g1879/DrissionPage/blob/0ec765e28ae0bc19fd7bca3ce2a00f8cb8337c6b/DrissionPage/_units/selector.py#L251-L269

values = ["rat", "bird", "dog", "cat", "cat"]

select_html = """
<select name="animals" id="animals">
  <option selected="selected" disabled="true">--Please Select --</option>
  <option value="spam1">spam</option>
  <option value="spam2">spam</option>
  <option value="spam3">spam</option>
  <option value="spam4">spam</option>
  <option value="spam5">spam</option>
  <option value="spam6">spam</option>
  <option value="spam7">spam</option>
  <option value="spam8">spam</option>
  <option value="spam9">spam</option>
  <option value="spam10">spam</option>
  <option value="spam11">spam</option>
  <option value="spam12">spam</option>
  <option value="spam13">spam</option>
  <option value="spam14">spam</option>
  <option value="spam15">spam</option>
  <option value="spam16">spam</option>
  <option value="spam17">spam</option>
  <option value="dog">Dog</option>
  <option value="spam18">spam</option>
  <option value="cat">Cat</option>
  <option value="bird">Bird</option>
  <option value="spam19">spam</option>
  <option value="rat">Rat</option>
  <option value="spam20">spam</option>
  <option value="spam21">spam</option>
</select>
"""

track_js = """
window.selected = undefined
window.trusted = undefined
var elem = document.getElementById("animals")
elem.addEventListener("change", (e)=>{window.selected=e.target.value; window.trusted = e.isTrusted});
"""


# doesn't have an effect
async def enter(tab: Target):
    # press enter on a TAB
    await asyncio.sleep(0.05)
    # press enter
    key_event = {
        "type": "keyDown",
        "code": "Enter",
        "windowsVirtualKeyCode": 13,
        "key": "Enter",
        "modifiers": 0
    }
    await tab.execute_cdp_cmd("Input.dispatchKeyEvent", key_event)
    await asyncio.sleep(0.05)
    key_event["type"] = "keyUp"
    await tab.execute_cdp_cmd("Input.dispatchKeyEvent", key_event)


# doesn't have an effect
async def down(tab: Target):
    # press enter on a TAB
    await asyncio.sleep(0.05)
    # press enter
    key_event = {
        "type": "keyDown",
        "code": "ArrowDown",
        "windowsVirtualKeyCode": 0x28,
        "nativeVirtualKeyCode": 0x28,
        "key": "ArrowDow",
        "keyIdentifier": "U+2193",
        "modifiers": 0,
        "commands": ["MoveDown"],
        "isSystemKey": False
    }
    await tab.execute_cdp_cmd("Input.dispatchKeyEvent", key_event)
    await asyncio.sleep(0.05)
    key_event["type"] = "keyUp"
    await tab.execute_cdp_cmd("Input.dispatchKeyEvent", key_event)


async def add_elem(driver: Chrome):
    await driver.current_target.set_source(select_html)
    await driver.execute_script(track_js, unique_context=False)


async def select_test(driver, subtests, headfull=False):
    await add_elem(driver)
    async_input = None
    if headfull:
        async_input = await AsyncInput(browser=driver)

    elem = await driver.find_element(By.ID, "animals")

    for i in range(10):
        if i != 0:
            vh = (i * 10)
            await elem.execute_script(f"""
                obj.style.cssText = `
                  position: fixed;
                  left: {vh}vw;
                  top: {vh}vh;
                `;
            """)

        for value in values:
            await select(elem, value, async_input=async_input)
            trusted, value_got = await driver.execute_script("return [window.trusted, window.selected]",
                                                             unique_context=False)
            with subtests.test():
                assert value == value_got
            with subtests.test():
                assert trusted
    with subtests.test():
        with pytest.raises(ValueError):
            elem = await driver.find_element(By.ID, "animals")
            await select(elem, "invalid", async_input=async_input)


@pytest.mark.skip("Wont fix")
@pytest.mark.asyncio
async def test_select(h_driver, subtests):
    await select_test(h_driver, subtests)


@pytest.mark.asyncio
async def test_select_headfull(driver, subtests):
    await select_test(driver, subtests, headfull=True)
