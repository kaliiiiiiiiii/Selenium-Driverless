from selenium_driverless.types.webelement import WebElement, ElementNotVisible
from selenium_driverless.webdriver import Chrome
import asyncio
import pytest
import inspect


@pytest.mark.asyncio
async def click_hit_test(elem: WebElement, subtests):
    original = await elem.execute_script('return [obj.style.left, obj.style.top, obj.style.position];')
    for i in range(5):
        x = y = f"{(i * 20) + 1}%"
        for _ in range(2):
            with subtests.test(x=x, y=y, test=inspect.stack()[1][3]):
                await elem.execute_script('var [x, y] = arguments;'
                                          'obj.style.position = "absolute";'
                                          'obj.style.left=x; obj.style.top = y', x, y)
                expect_click = asyncio.ensure_future(
                    elem.eval_async('return await new Promise((resolve)=>{obj.addEventListener("click", resolve)})'))
                await asyncio.sleep(0.001)
                await elem.click(move_to=False)
                try:
                    await asyncio.wait_for(expect_click, 3)
                except asyncio.TimeoutError:
                    raise asyncio.TimeoutError("Click did not hit element within 3 seconds")
    await elem.execute_script(
        'obj.style.left = arguments[0];'
        'obj.style.top = arguments[1];'
        'obj.style.position = arguments[2];',
        *original
    )


async def zero_height_test(elem: WebElement, subtests):
    padding = "2.5%"
    original_styles = await elem.execute_script(
        'const orig_styles = [obj.style.height, obj.style.width, obj.style.padding];'
        'obj.style.height = "0"; obj.style.width = "0"; obj.style.padding = arguments[0];'
        'return orig_styles;', padding)
    await click_hit_test(elem, subtests)
    await elem.execute_script(
        'obj.style.height = arguments[0]; obj.style.width = arguments[1];'
        'obj.style.padding = arguments[2];',
        *original_styles)


async def zero_height_and_padding_test(elem: WebElement, subtests):
    border = "5% solid black"
    original_styles = await elem.execute_script(
        'const orig_styles = [obj.style.height, obj.style.width, '
        '           obj.style.padding, obj.style.border];'
        'obj.style.height = "0"; obj.style.width = "0";  obj.style.padding = "0"; '
        'obj.style.border = arguments[0];'
        'return orig_styles;', border)
    await click_hit_test(elem, subtests)
    await elem.execute_script(
        'obj.style.height = arguments[0]; obj.style.width = arguments[1]; '
        'obj.style.padding = arguments[2]; obj.style.border = arguments[3]',
        *original_styles)


async def all_zero_test(elem, subtests, expect_fail=True):
    original_styles = await elem.execute_script(
        'const orig_styles = [obj.style.height, obj.style.width, obj.style.padding, obj.style.borderWidth];'
        'obj.style.height = "0";'
        'obj.style.width = "0";'
        'obj.style.padding = "0";'
        'obj.style.borderWidth = "0";'
        'return orig_styles;'
    )
    if expect_fail:
        await expect_not_visible(elem, subtests)
    else:
        await click_hit_test(elem, subtests)
    await elem.execute_script(
        'obj.style.height = arguments[0];'
        'obj.style.width = arguments[1];'
        'obj.style.padding = arguments[2];'
        'obj.style.borderWidth = arguments[3];',
        *original_styles
    )


async def display_none_expect_fail(elem: WebElement, subtests):
    original_display = await elem.execute_script('const original = obj.style.display;'
                                                 'obj.style.display = "none";'
                                                 'return original')
    await expect_not_visible(elem, subtests)
    await elem.execute_script("obj.style.display = arguments[0]", original_display)


async def outside_viewport_expect_fail(elem: WebElement, subtests):
    original_position = await elem.execute_script(
        'const original = [obj.style.left, obj.style.top, obj.style.position];'
        'obj.style.position = "absolute";'
        'obj.style.left = "-9999px";'
        'return original;'
    )
    await expect_not_visible(elem, subtests)
    await elem.execute_script(
        'obj.style.left = arguments[0];'
        'obj.style.top = arguments[1];'
        'obj.style.position = arguments[2];',
        *original_position
    )


async def scroll_and_click_test(elem: WebElement, driver: Chrome, subtests):
    original_position = await elem.execute_script(
        'const original = [obj.style.left, obj.style.top, obj.style.position];'
        'obj.style.top = "200vh";'
        'obj.style.left = "200vh";'
        'obj.style.position = "relative";'
        'return original;'
    )
    await driver.execute_script(
        'document.body.style.height = "300vh";'
        'document.body.style.width = "300vh";'
        'const div = document.createElement("div");'
        'div.style.height = "200vh";div.style.width = "200vh";'
        'document.body.appendChild(div);'
    )
    with subtests.test(test=inspect.stack()[1][3]):
        await elem.click()

    await elem.execute_script(
        'obj.style.left = arguments[0];'
        'obj.style.top = arguments[1];'
        'obj.style.position = arguments[2];'
        'document.body.style.height = "";document.body.style.width = "";'
        'document.body.querySelector("div").remove();',
        *original_position
    )


async def expect_not_visible(elem: WebElement, subtests):
    with subtests.test(test=inspect.stack()[1][3]):
        with pytest.raises(ElementNotVisible):
            await elem.mid_location()
    with subtests.test(test=inspect.stack()[1][3]):
        with pytest.raises(asyncio.TimeoutError):
            await elem.click(move_to=False, visible_timeout=1)


async def all_test(elem: WebElement, driver, subtests, only_border_test=True, expect_all_zero_fail=True):
    await all_zero_test(elem, subtests, expect_fail=expect_all_zero_fail)
    if only_border_test:
        await zero_height_and_padding_test(elem, subtests)
    await zero_height_test(elem, subtests)
    await display_none_expect_fail(elem, subtests)
    await outside_viewport_expect_fail(elem, subtests)
    await click_hit_test(elem, subtests)
    await scroll_and_click_test(elem, driver, subtests)
    pass


@pytest.mark.asyncio
async def test_button(h_driver, subtests):
    button = await h_driver.execute_script(
        """
        const elem = document.createElement("button");
        elem.style.height = "5%"; elem.style.width = "5%";
        elem.style.backgroundColor = "grey";
        document.body.appendChild(elem);
        return elem
        """
    )
    await all_test(button, h_driver, subtests, only_border_test=False)


@pytest.mark.asyncio
async def test_div(h_driver, subtests):
    button = await h_driver.execute_script(
        """
        const elem = document.createElement("div");
        elem.style.height = "5%"; elem.style.width = "5%";
        elem.style.backgroundColor = "grey";
        document.body.appendChild(elem);
        return elem
        """
    )
    await all_test(button, h_driver, subtests, only_border_test=False)


@pytest.mark.asyncio
async def test_input(h_driver, subtests):
    button = await h_driver.execute_script(
        """
        const elem = document.createElement("input");
        elem.style.height = "5%"; elem.style.width = "5%";
        elem.style.backgroundColor = "grey";
        document.body.appendChild(elem);
        return elem
        """
    )
    await all_test(button, h_driver, subtests)


@pytest.mark.asyncio
async def test_rotated_long_table(h_driver, subtests):
    table = await h_driver.execute_script(
        """
        const table = document.createElement("table");
        table.style.borderCollapse = "collapse";
        table.style.transform = "rotate(40deg)";
        table.style.width = "15%";
        table.style.position = "absolute";
        table.style.transformOrigin = "top left";

        for (let i = 0; i < 10; i++) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.textContent = "Row " + (i + 1);
            cell.style.border = "1px solid black";
            cell.style.padding = "5px";
            row.appendChild(cell);
            table.appendChild(row);
        }

        document.body.appendChild(table);
        return table;
        """
    )
    # Call a function to run your tests on the created table
    await all_test(table, h_driver, subtests, expect_all_zero_fail=False)

