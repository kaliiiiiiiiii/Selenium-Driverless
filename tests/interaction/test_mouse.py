import typing

import pytest
import time
from cdp_patches.input import AsyncInput
from selenium_driverless.types.deserialize import JSFunction, JSWindow
from selenium_driverless.types.webelement import WebElement

special = object()

script = """
    window.events = []
    b = document.body
    function jsonify(e){
        if (e !== Object(e)){
            // is primitive value
            return e
        }
        var res = {}
        var val
        for (key in e){
            res[key]=e[key]
        }
        return res
    }
    
    function h(e){
        var res = jsonify(e)
        res["sourceCapabilities"] = jsonify(e.sourceCapabilities)
        window.events.push(res)
    }
    b.addEventListener("click", h)
    b.addEventListener("mousedown", h)
    b.addEventListener("mouseup", h)
    """

mouse_event_expected = {
    "isTrusted": True,
    "ctrlKey": False,
    "shiftKey": False,
    "altKey": False,
    "metaKey": False,
    "button": 0,
    "buttons": 0,
    "relatedTarget": None,
    "movementX": 0,
    "movementY": 0,
    "fromElement": None,
    "detail": 1,
    "which": 1,
    "eventPhase": 2,
    "bubbles": True,
    "cancelable": True,
    "defaultPrevented": False,
    "composed": True,
    "returnValue": True,
    "cancelBubble": False,
    "NONE": 0,
    "CAPTURING_PHASE": 1,
    "AT_TARGET": 2,
    "BUBBLING_PHASE": 3
}
mouse_expected_keys = {"screenX", "screenY", "clientX", "clientY",
                       "pageX", "pageY", "x", "y", 'offsetX', 'offsetY', "layerX", "layerY",
                       'getModifierState', 'initMouseEvent', 'initUIEvent', 'currentTarget',
                       'stopPropagation', 'timeStamp', "sourceCapabilities", 'srcElement',
                       'composedPath', 'initEvent', 'preventDefault', 'stopImmediatePropagation',
                       "view", "target", "type", "toElement"}

click_expected = {
    "azimuthAngle": 0,
    "height": 1,
    "tiltX": 0,
    "tiltY": 0,
    "pointerType": "mouse",
    "tangentialPressure": 0,
    "twist": 0,
    "isPrimary": False,
    "pointerId": 1,
    "width": 1,
    "pressure": 0,
}
click_expected_keys = {
    'getPredictedEvents',
    'getCoalescedEvents',
    "altitudeAngle"
}
mousedown_expected = {
    "buttons": 1,
}


def in_range(num, expected, _range):
    return (expected + _range) >= num >= (expected - _range)


def validate_mouse_event(subtests, event: dict, x, y, time_origin: float,
                         _type: typing.Literal["mousedown", "mouseup", "click"],
                         timestamp_range=2, pixel_range=1):
    now = time.time()

    expected = mouse_event_expected.copy()
    expected.update(mouse_event_expected)
    if _type == "click":
        expected.update(click_expected)
    elif _type == "mousedown":
        expected.update(mousedown_expected)

    expected_keys = mouse_expected_keys.copy()
    expected_keys.update(expected.keys())
    if _type == "click":
        expected_keys.update(click_expected_keys)

    for key, value in event.items():
        expected_value = expected.get(key, special)
        if expected_value == special:
            # no constant == assertion
            with subtests.test():
                if key in expected_keys:
                    expected_keys.remove(key)
                if key in ['getCoalescedEvents', 'getPredictedEvents', 'getModifierState', 'initMouseEvent',
                           'initUIEvent',
                           'stopPropagation', 'composedPath', 'initEvent', 'preventDefault',
                           'stopImmediatePropagation']:
                    assert isinstance(value, JSFunction)
                elif key == "screenX":
                    assert not in_range(value, x, pixel_range)
                elif key == "screenY":
                    assert not in_range(value, y, pixel_range)
                elif key in ["clientX", "x"]:
                    assert in_range(value, x, pixel_range)
                elif key in ["clientY", "y"]:
                    assert in_range(value, y, pixel_range)
                elif key == "pageX":
                    pass
                    # todo: assert
                    # assert value == x
                elif key == "pageY":
                    pass
                    # todo: assert
                    # assert value == y
                elif key == 'offsetX':
                    pass
                    # todo: assert
                    # assert value == x
                elif key == 'offsetY':
                    pass
                    # todo: assert
                    # assert value == y
                elif key == "layerX":
                    pass
                    # todo:
                    # assert value == x
                elif key == "layerY":
                    pass
                    # todo:
                    # assert value == y
                elif key in ['currentTarget', 'srcElement', "target"]:
                    assert (isinstance(value, WebElement) or value is None)
                elif key == 'timeStamp':

                    # timeStamp to UTC in seconds
                    value = (time_origin + value) / 1000

                    # maximum timestamp_range ago
                    assert value <= now
                    assert value >= (now - timestamp_range)
                elif key == "sourceCapabilities":
                    assert len(value) == 1
                    assert value["firesTouchEvents"] is False
                elif key == "view":
                    assert (isinstance(value, JSWindow) or value is None)
                elif key == "altitudeAngle":
                    # 90° in rad expected
                    assert in_range(value, 1.5708, 0.0001)
                elif key == "type":
                    assert value == _type
                elif key == "toElement":
                    if _type == "click":
                        assert value is None
                    else:
                        assert isinstance(value, WebElement)
                else:
                    raise ValueError(
                        f"Got unknown, unexpected attribute for event\n {key.__repr__()}={value.__repr__()}")
        else:
            expected_keys.remove(key)

            with subtests.test(key=key):
                assert value == expected_value
    with subtests.test():
        assert len(expected_keys) == 0


async def click_tester(subtests, driver, cdp_patches=False):
    await driver.current_target.execute_script(script)
    event_types = ["mousedown", "mouseup", "click"]
    cords = [
        [100, 50],
        [200, 100],
        [300, 150]
    ]

    if cdp_patches:
        p = await AsyncInput(browser=driver, emulate_behaviour=False)
        for x, y in cords:
            await p.click("left", x, y)
    else:
        p = driver.current_pointer
        for x, y in cords:
            await p.click(x, y, move_to=False)

    events, time_origin = await driver.execute_script("return [window.events, performance.timeOrigin]", max_depth=10)
    assert len(events) == len(cords) * 3

    for idx in range(len(cords)):
        x, y = cords[idx]
        grouped_events = events[idx * 3:(idx * 3) + 3]
        for _type, event in zip(event_types, grouped_events):
            validate_mouse_event(subtests, event, x, y, time_origin, _type)


@pytest.mark.asyncio
async def test_click(driver, subtests):
    await click_tester(subtests, driver)


@pytest.mark.skip(reason="Headless will always fail")
@pytest.mark.asyncio
async def test_headless_click(h_driver, subtests):
    await click_tester(subtests, h_driver)


@pytest.mark.asyncio
async def test_click_with_cdp_patches(driver, subtests):
    await click_tester(subtests, driver, cdp_patches=True)
