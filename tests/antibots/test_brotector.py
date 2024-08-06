import asyncio
import pytest
from selenium_driverless.types.by import By
import typing
from selenium_driverless.types.target import Target
from cdp_patches.input import AsyncInput


async def detect(target: Target, cdp_patches_input: typing.Union[AsyncInput, typing.Literal[False, None]] = False):
    script = """
        await brotector.init_done; 
        return brotector.detections
    """
    await target.get("https://kaliiiiiiiiii.github.io/brotector/")
    await asyncio.sleep(0.5)
    click_target = await target.find_element(By.ID, "copy-button")
    if cdp_patches_input:
        x, y = await click_target.mid_location()
        await cdp_patches_input.click("left", x, y)
    else:
        await click_target.click()
    await asyncio.sleep(0.5)
    for _ in range(2):
        detections = await target.eval_async(script)
        assert len(detections) == 0


@pytest.mark.skip(reason="CDP isn't integrated automatically yet")
@pytest.mark.asyncio
@pytest.mark.skip_offline
async def test_driverless(driver):
    await detect(driver.current_target, cdp_patches_input=False)


@pytest.mark.asyncio
@pytest.mark.skip_offline
async def test_driverless_with_cdp_patches(driver):
    await detect(driver.current_target, cdp_patches_input=await AsyncInput(browser=driver))


@pytest.mark.skip(reason="Headless will always fail")
@pytest.mark.asyncio
@pytest.mark.skip_offline
async def test_headless(h_driver):
    await detect(h_driver.current_target, cdp_patches_input=False)
