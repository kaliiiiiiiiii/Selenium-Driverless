import asyncio
import pytest
from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException


@pytest.mark.asyncio
@pytest.mark.skip_offline
async def test_bypass_turnstile(driver):
    await driver.get("https://nopecha.com/demo/turnstile")
    await asyncio.sleep(0.5)

    # some random mouse-movements over iframes
    pointer = driver.current_pointer
    await pointer.move_to(500, 200, smooth_soft=60, total_time=0.5)
    await pointer.move_to(20, 50, smooth_soft=60, total_time=0.5)
    await pointer.move_to(8, 45, smooth_soft=60, total_time=0.5)
    await pointer.move_to(500, 200, smooth_soft=60, total_time=0.5)
    await pointer.move_to(166, 206, smooth_soft=60, total_time=0.5)
    await pointer.move_to(200, 205, smooth_soft=60, total_time=0.5)

    wrappers = await driver.find_elements(By.XPATH, '//*[@class="cf-turnstile-wrapper"]')
    await asyncio.sleep(0.5)

    shadow_document = None
    passed = False
    for wrapper in wrappers:
        # filter out correct iframe document
        shadow_document = await wrapper.shadow_root
        if shadow_document:
            iframe = await shadow_document.find_element(By.CSS_SELECTOR, "iframe")
            content_document = await iframe.content_document
            body = await content_document.execute_script("return document.body", unique_context=True)
            nested_shadow_document = await body.shadow_root
            try:
                checkbox = await nested_shadow_document.find_element(By.CSS_SELECTOR,"input[type='checkbox']",timeout=5)
            except NoSuchElementException:
                pass
            else:
                await checkbox.click(move_to=True)
                await checkbox.execute_script("console.log(obj)")
                try:
                    await nested_shadow_document.find_element(By.CSS_SELECTOR, "#success", timeout=20)
                    passed = True
                except (NoSuchElementException, asyncio.TimeoutError):
                    passed = False
                assert passed
