from selenium_driverless.types.by import By
from cdp_patches.input import AsyncInput
from selenium_driverless.types.webelement import NoSuchElementException
import asyncio
import pytest


async def bet365_test(driver, async_input: AsyncInput = None):
    async def click_login(timeout: float = 30):
        login_button = await driver.find_element(By.XPATH, value='//*[@class="hm-MainHeaderRHSLoggedOutWide_Join "]',
                                                 timeout=timeout)
        if async_input is None:
            await login_button.click()
        else:
            x, y = await login_button.mid_location()
            await async_input.click("left", x, y)

    await driver.focus()
    await driver.get('https://www.365365824.com/#/IP/B16', wait_load=True)
    await asyncio.sleep(1)
    await click_login()
    await asyncio.sleep(1)
    try:
        await click_login(timeout=3)
    except (NoSuchElementException, asyncio.TimeoutError):
        pass
    await asyncio.sleep(3)
    url = await driver.current_url
    assert url[:31] == "https://www.365365824.com/#/ME/"


@pytest.mark.skip(reason="Passes anyways if headless passes")
@pytest.mark.asyncio
@pytest.mark.skip_offline
async def test_headfull_bet365(driver):
    await bet365_test(driver)


@pytest.mark.asyncio
@pytest.mark.skip_offline
async def test_headless_bet365(h_driver):
    await bet365_test(h_driver)
