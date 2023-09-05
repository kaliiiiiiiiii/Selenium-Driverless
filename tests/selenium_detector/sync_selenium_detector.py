import asyncio

from selenium_driverless.sync import webdriver
from selenium_driverless.types.by import By

options = webdriver.ChromeOptions()
with webdriver.Chrome(options=options) as driver:
    driver.get('https://hmaker.github.io/selenium-detector/')
    elem = driver.find_element(By.CSS_SELECTOR, "#chromedriver-token")
    driver.execute_script("console.log(arguments[0])", elem)
    elem.write(driver.execute_script('return window.token'))
    elem2 = driver.find_element(By.CSS_SELECTOR, "#chromedriver-asynctoken")
    async_token = driver.execute_async_script('window.getAsyncToken().then(arguments[0])')
    elem2.write(async_token)
    elem3 = driver.find_element(By.CSS_SELECTOR, "#chromedriver-test")
    driver.sleep(0.2)
    elem3.click()
    print(driver.title)
