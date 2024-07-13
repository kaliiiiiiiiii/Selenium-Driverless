from selenium_driverless.types.by import By
from selenium_driverless.types.target import Target
import pytest
@pytest.mark.asyncio_cooperative
async def test_detector(h_tab: Target):
    await h_tab.get('https://hmaker.github.io/selenium-detector/')
    elem = await h_tab.find_element(By.CSS_SELECTOR, "#chromedriver-token")
    await elem.send_keys(await h_tab.execute_script('return window.token'))
    elem2 = await h_tab.find_element(By.CSS_SELECTOR, "#chromedriver-asynctoken")
    async_token = await h_tab.eval_async('return await window.getAsyncToken()')
    await elem2.send_keys(async_token)
    elem3 = await h_tab.find_element(By.CSS_SELECTOR, "#chromedriver-test")
    await elem3.click()
    passed = await h_tab.find_element(By.XPATH, '//*[@id="chromedriver-test-container"]/span')
    text = await passed.text
    assert text == "Passed!"
