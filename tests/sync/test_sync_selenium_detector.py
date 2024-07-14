import pytest

from selenium_driverless.types.by import By


@pytest.mark.skip_offline
def test_sync_selenium_detector(sync_h_driver):
    sync_h_driver.get('https://hmaker.github.io/selenium-detector/')
    elem = sync_h_driver.find_element(By.CSS_SELECTOR, "#chromedriver-token")

    elem.write(sync_h_driver.execute_script('return window.token'))
    elem2 = sync_h_driver.find_element(By.CSS_SELECTOR, "#chromedriver-asynctoken")
    async_token = sync_h_driver.eval_async('return await window.getAsyncToken()')
    elem2.write(async_token)
    elem3 = sync_h_driver.find_element(By.CSS_SELECTOR, "#chromedriver-test")
    elem.execute_script("console.log(arguments); try{throw new Error()} catch(e){console.error(e)}", elem, elem2, elem3, unique_context=False)
    sync_h_driver.sleep(0.2)
    elem3.click()
    passed = sync_h_driver.find_element(By.XPATH, '//*[@id="chromedriver-test-container"]/span')
    text = passed.text
    assert text == "Passed!"
    print(text)
