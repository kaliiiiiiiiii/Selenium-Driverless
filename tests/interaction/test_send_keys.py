import asyncio

import pytest
from selenium_driverless.types.target import KEY_MAPPING
from selenium_driverless.types.webelement import WebElement


@pytest.mark.asyncio
async def test_assert_chars(h_driver, subtests):
    target = h_driver.current_target
    elem = await target.execute_script("""
        const elem = document.createElement("textarea")
        document.body.appendChild(elem)
        return elem
    """)
    assert isinstance(elem, WebElement)
    for key in KEY_MAPPING.keys():
        with subtests.test(key=key):
            await elem.send_keys(key, click_on=False)
            value = await elem.execute_script("return obj.value")
            if key == "\r":
                key = "\n"
            assert value == key
            await elem.execute_script("obj.value=''; obj.textContent=''")
            await asyncio.sleep(0.01)
