from selenium_driverless.sync import webdriver

options = webdriver.ChromeOptions()
with webdriver.Chrome(options=options) as driver:
    driver.get('https://abrahamjuliot.github.io/creepjs/')
    print(driver.title)
