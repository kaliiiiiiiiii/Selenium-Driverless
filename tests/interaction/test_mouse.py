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
        var res = {}
        var val
        for (key in e){
            val = e[key]
            if (key === "timeStamp" && typeof val === "number"){
                // normalize timestamp to UTC seconds
                val = (val + performance.timeOrigin)/1000
            }else if (key === "sourceCapabilities"){
                var _val = jsonify(val)
                val = _val
                key = "sourceCapabilities"
            }
            res[key]=val
        }
        return res
    }
    
    function h(e){
        window.events.push(jsonify(e))
    }
    b.addEventListener("click", h)
    """

click_expected = {
    "isTrusted": True,
    "pointerId": 1,
    "width": 1,
    "height": 1,
    "pressure": 0,
    "tiltX": 0,
    "tiltY": 0,
    "azimuthAngle": 0,
    "tangentialPressure": 0,
    "twist": 0,
    "pointerType": "mouse",
    "isPrimary": False,
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
    "toElement": None,
    "detail": 1,
    "which": 1,
    "type": "click",
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


def in_range(num, expected, _range):
    return (expected + _range) >= num >= (expected - _range)


def validate_click_event(event: dict, x, y, timestamp_range=2, pixel_range=1):
    now = time.time()
    expected_keys = {'getCoalescedEvents', 'getPredictedEvents', "screenX", "screenY", "clientX", "clientY",
                     "pageX", "pageY", "x", "y", 'offsetX', 'offsetY', "layerX", "layerY", 'getModifierState',
                     'initMouseEvent', 'initUIEvent', 'currentTarget', 'stopPropagation', 'timeStamp',
                     "sourceCapabilities",
                     'srcElement', 'composedPath', 'initEvent', 'preventDefault', 'stopImmediatePropagation', "view",
                     "target", "altitudeAngle"}
    for key in click_expected.keys():
        expected_keys.add(key)

    for key, value in event.items():
        expected_value = click_expected.get(key, special)
        if expected_value == special:
            if key in expected_keys:
                expected_keys.remove(key)
            if key in ['getCoalescedEvents', 'getPredictedEvents', 'getModifierState', 'initMouseEvent', 'initUIEvent',
                       'stopPropagation', 'composedPath', 'initEvent', 'preventDefault', 'stopImmediatePropagation']:
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
            else:
                raise ValueError(f"Got unknown, unexpected attribute for event\n {key.__repr__()}={value.__repr__()}")
        else:
            expected_keys.remove(key)
            if not (value == expected_value):
                print()
            assert value == expected_value
    assert len(expected_keys) == 0


async def click_tester(driver, cdp_patches=False):
    await driver.current_target.execute_script(script)
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

    events = await driver.execute_script("return window.events", max_depth=10)
    assert len(events) == 3
    for idx, event in enumerate(events):
        x, y = cords[idx]
        validate_click_event(event, x, y)


@pytest.mark.asyncio
async def test_click(driver):
    await click_tester(driver)


@pytest.mark.skip(reason="Headless will always fail")
@pytest.mark.asyncio
async def test_headless_click(h_driver):
    await click_tester(h_driver)


@pytest.mark.asyncio
async def test_click_with_cdp_patches(driver):
    await click_tester(driver, cdp_patches=True)
