from selenium_driverless.types.by import By
import asyncio
import pytest


@pytest.mark.asyncio
@pytest.mark.skip_offline
async def test_headfull_bet365(driver):
    async def click_login():
        login_button = await driver.find_element(By.XPATH, value='//*[@class="hm-MainHeaderRHSLoggedOutWide_Join "]', timeout=30)
        await login_button.click()

    await driver.focus()
    await driver.get('https://www.365365824.com/#/IP/B16', wait_load=True)
    await asyncio.sleep(1)
    await click_login()
    await asyncio.sleep(3)
    url = await driver.current_url
    assert url[:31] == "https://www.365365824.com/#/ME/"
