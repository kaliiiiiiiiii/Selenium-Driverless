from selenium_driverless.types.by import By
from selenium_driverless.types.target import Target
import pytest


@pytest.mark.asyncio
async def test_detector(h_driver: Target):
    await h_driver.get('https://hmaker.github.io/selenium-detector/')
    elem = await h_driver.find_element(By.CSS_SELECTOR, "#chromedriver-token")
    await elem.write(await h_driver.execute_script('return window.token'))
    elem2 = await h_driver.find_element(By.CSS_SELECTOR, "#chromedriver-asynctoken")
    async_token = await h_driver.eval_async('return await window.getAsyncToken()')
    await elem2.write(async_token)
    elem3 = await h_driver.find_element(By.CSS_SELECTOR, "#chromedriver-test")
    await elem3.click()
    passed = await h_driver.find_element(By.XPATH, '//*[@id="chromedriver-test-container"]/span')
    text = await passed.text
    assert text == "Passed!"
