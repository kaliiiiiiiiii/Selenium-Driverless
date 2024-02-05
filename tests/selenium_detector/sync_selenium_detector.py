from selenium_driverless.sync import webdriver
from selenium_driverless.types.by import By


options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
with webdriver.Chrome(options=options) as driver:
    driver.get('https://hmaker.github.io/selenium-detector/')
    elem = driver.find_element(By.CSS_SELECTOR, "#chromedriver-token")

    elem.write(driver.execute_script('return window.token'))
    elem2 = driver.find_element(By.CSS_SELECTOR, "#chromedriver-asynctoken")
    async_token = driver.eval_async('return await window.getAsyncToken()')
    elem2.write(async_token)
    elem3 = driver.find_element(By.CSS_SELECTOR, "#chromedriver-test")
    elem.execute_script("console.log(arguments); try{throw new Error()} catch(e){console.error(e)}", elem, elem2, elem3, unique_context=False)
    driver.sleep(0.2)
    elem3.click()
    passed = driver.find_element(By.XPATH, '//*[@id="chromedriver-test-container"]/span')
    text = passed.text
    assert text == "Passed!"
    print(text)
