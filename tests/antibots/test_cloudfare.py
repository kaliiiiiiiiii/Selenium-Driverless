import asyncio
import pytest
from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException


@pytest.mark.asyncio
@pytest.mark.skip_offline
async def test_bypass_turnstile(h_driver, subtests):
    await h_driver.get("https://nopecha.com/demo/turnstile")
    await asyncio.sleep(0.5)

    # some random mouse-movements over iframes
    pointer = h_driver.current_pointer
    await pointer.move_to(500, 200, smooth_soft=60, total_time=0.5)
    await pointer.move_to(20, 50, smooth_soft=60, total_time=0.5)
    await pointer.move_to(8, 45, smooth_soft=60, total_time=0.5)
    await pointer.move_to(500, 200, smooth_soft=60, total_time=0.5)
    await pointer.move_to(166, 206, smooth_soft=60, total_time=0.5)
    await pointer.move_to(200, 205, smooth_soft=60, total_time=0.5)

    wrappers = await h_driver.find_elements(By.XPATH, '//*[@class="turnstile"]')
    await asyncio.sleep(0.5)

    for wrapper in wrappers:
        with subtests.test(wrapper=wrapper):
            # filter out correct iframe document
            inner = await wrapper.execute_script("return obj.children[0].children[0]")
            shadow_document = await inner.shadow_root

            iframe = await shadow_document.find_element(By.CSS_SELECTOR, "iframe")
            content_document = await iframe.content_document
            body = await content_document.execute_script("return document.body", unique_context=True)
            nested_shadow_document = await body.shadow_root
            try:
                await nested_shadow_document.find_element(By.CSS_SELECTOR, "#success", timeout=4)
                # already passed
            except (NoSuchElementException, asyncio.TimeoutError):
                checkbox = await nested_shadow_document.find_element(By.CSS_SELECTOR,"input[type='checkbox']",timeout=10)
                await checkbox.click(move_to=True)
                await checkbox.execute_script("console.log(obj)")
                await nested_shadow_document.find_element(By.CSS_SELECTOR, "#success", timeout=20)
