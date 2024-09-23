from selenium_driverless.types.webelement import WebElement
from selenium_driverless.types import JSEvalException
import asyncio
from typing import Type
try:
    from cdp_patches.input import AsyncInput
    from cdp_patches.input import KeyboardCodes
except ImportError:
    # noinspection PyTypeChecker
    AsyncInput: Type["AsyncInput"] = "AsyncInput"
    KeyboardCodes: Type["KeyboardCodes"] = "KeyboardCodes"


async def select(elem: WebElement, value: str = None, text: str = None, async_input: AsyncInput = None,
                 timeouts: float = 0.01) -> None:
    """
    Selects an option of a ``<select>`` element

    :param elem: ``<select>`` element to select an option from
    :param value: value for the option to select (can be different from the text!)
    :param text: the text of the option to select
    :param async_input: an instance of ``cdp_patches.input.AsyncInput``
    :param timeouts: timeout in seconds between actions performed to select an option

    .. warning::
        this is potentially detectable without the use of `CDP-patches <https://github.com/Kaliiiiiiiiii-Vinyzu/CDP-Patches>`_ !
    """
    use_js = async_input is None
    if use_js:
        await elem.click()
    else:
        x, y = await elem.mid_location()
        await async_input.click("left", x, y)
    if value is None and text is None:
        raise ValueError("value or text need to be specified")
    try:
        n, direction = await elem.execute_script("""
            let [value, text, use_js] = arguments
            var idx = Array.from(obj.options).findIndex(option => option.value === value || option.text === text)
            var currIdx = obj.selectedIndex
            if (idx === -1){throw ReferenceError("option not found")}
            if(typeof value == 'undefined'){
                value = obj.options[idx].value
            }
            if(use_js && obj.options[currIdx].value !== value){
                obj.value = value
                const evt = new Event("change")
                evt.initEvent("change", true, true)
                obj.dispatchEvent(evt)
                return [0, 1]
            }else{
                const n = Math.abs(idx - currIdx);
                const direction = idx < currIdx ? 1 : -1
                return [n, direction]
            }

        """, value, text, use_js)
    except JSEvalException as e:
        if e.class_name == "ReferenceError" and e.description[:33] == 'ReferenceError: option not found\n':
            raise ValueError(f"option not found based on value:{value}, text:{text} for {elem}")
        raise e
    if use_js is False:
        if direction == 1:
            code = KeyboardCodes.UP_ARROW
        else:
            code = KeyboardCodes.DOWN_ARROW
        for _ in range(n):
            await asyncio.sleep(timeouts)
            async_input.base.send_keystrokes(code)
        await asyncio.sleep(timeouts)
        x, y = await elem.mid_location()
        await async_input.click("left", x, y)
        await asyncio.sleep(timeouts)
