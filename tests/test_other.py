import asyncio
import pytest


@pytest.mark.asyncio
async def test_prompt(driver):
    await driver.get("chrome://version")
    keys = "Hello!"
    fut = asyncio.ensure_future(driver.execute_script("return prompt('hello?')", timeout=100))
    await asyncio.sleep(0.5)
    alert = await driver.current_target.get_alert(timeout=5)
    await alert.send_keys(keys)
    res = await fut
    assert res == keys
