from selenium_driverless.types.by import By
import pytest

dl_len = 12
relative_html = ""
for i in range(1, dl_len + 1):
    relative_html += f'<dl class="test_cls"><span class="test_sub_cls">Element{i}</span></dl>\n'


@pytest.mark.asyncio
async def relative_test(driver, subtests, by, value):
    # Load the static HTML content
    await driver.current_target.set_source(relative_html)

    # Find the elements as per the main function logic
    dl_list = await driver.find_elements(By.CSS_SELECTOR, 'dl.test_cls')
    with subtests.test():
        assert len(dl_list) == dl_len
    for idx, dl in enumerate(dl_list):
        idx += 1
        elem = await dl.find_element(by, value)

        texts = [await dl.text, await elem.text]
        for text in texts:
            with subtests.test():
                assert text == f'Element{idx}'


@pytest.mark.asyncio
async def test_relative_xpath(h_driver, subtests):
    # also includes By.ID, By.CLASS_NAME, By.NAME - see https://github.com/kaliiiiiiiiii/Selenium-Driverless/blob/91273f1dd5bf0fea8c88f478cb209e6326e3ed34/src/selenium_driverless/types/webelement.py#L288-L296
    await relative_test(h_driver, subtests, By.XPATH, './/span[@class="test_sub_cls"]')


@pytest.mark.asyncio
async def test_relative_tag_name(h_driver, subtests):
    await relative_test(h_driver, subtests, By.TAG_NAME, 'span')


@pytest.mark.asyncio
async def test_relative_tag_name(h_driver, subtests):
    await relative_test(h_driver, subtests, By.TAG_NAME, 'span')


@pytest.mark.asyncio
async def test_relative_css(h_driver, subtests):
    # alias to By.CSS_SELECTOR
    await relative_test(h_driver, subtests, By.CSS, '.test_sub_cls')
