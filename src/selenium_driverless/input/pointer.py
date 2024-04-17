import asyncio
import time
import inspect
import typing

import numpy as np

from selenium_driverless.scripts.geometry import gen_combined_path, pos_at_time, bias_0_dot_5


def make_rand_click_timeout():
    return 0.125 + (bias_0_dot_5(0.5, 0.5) - 0.5) / 10
    # => should be about 130ms +/-50


class Modifiers:
    NONE = 0
    """no modifier"""

    ALT = 1
    """alt modifier"""

    CTRL = 2
    """CTRL modifier"""

    COMMAND = 4
    """COMMAND modifier"""

    SHIFT = 8
    """SHIFT modifier"""


class PointerType:
    MOUSE = "mouse"
    """mousePointer"""

    PEN = "pen"
    """a pointer of type \"pen\""""


class MouseButton:
    """main button pressed"""

    NONE = "none"
    """no mouse button"""

    LEFT = "left"
    """left mouse button"""

    MIDDLE = "middle"
    """middle mouse button"""

    RIGHT = "right"
    """right mouse button"""

    BACK = "back"
    """back mouse button"""

    FORWARD = "forward"
    """forward mouse button"""


class Buttons:
    """modifier mouse button"""

    NONE = 0
    """no button"""

    LEFT = 1
    """left mouse button"""

    RIGHT = 2
    """right mouse button"""

    MIDDLE = 4
    """middle mouse button"""

    BACK = 8
    """back mouse button"""

    FORWARD = 16
    """forward mouse button"""

    DEFAULT = None
    """no modifier mouse button specified"""


class EventType:
    PRESS = "mousePressed"
    """mousePressed"""

    RELEASE = "mouseReleased"
    """mouseReleased"""

    MOVE = "mouseMoved"
    """mouseMoved"""

    WHEEL = "mouseWheel"
    """mouseWheel"""


class PointerEvent:
    # noinspection GrazieInspection
    def __init__(self, type_: str, x: int, y: int,
                 modifiers: int = Modifiers.NONE,
                 timestamp: float = None, button: str = MouseButton.LEFT, buttons: int = Buttons.DEFAULT,
                 click_count: int = 0, force: float = 0, tangential_pressure: float = 0,
                 tilt_x: float = 0, tilt_y: float = 0, twist: float = 0, delta_x: int = 0, delta_y: int = 0,
                 pointer_type: str = PointerType.MOUSE):
        """
        see `Input.dispatchMouseEvent <https://chromedevtools.github.io/devtools-protocol/tot/Input/#method-dispatchMouseEvent>`_ for reference
        """
        self._command = "Input.dispatchMouseEvent"

        self.type_ = type_
        self.x = x
        self.y = y
        self.modifiers = modifiers
        self.timestamp = timestamp
        self.button = button
        self.buttons = buttons
        self.click_count = click_count
        self.force = force
        self.tangential_pressure = tangential_pressure
        self.tilt_x = tilt_x
        self.tilt_y = tilt_y
        self.twist = twist
        self.delta_x = delta_x
        self.delta_y = delta_y
        self.pointer_type = pointer_type

    def to_json(self) -> typing.List[typing.Union[str, typing.Dict[str, typing.Union[int, str]]]]:
        """the event as JSON"""
        _json = {
            "type": self.type_,
            "x": self.x,
            "y": self.y,
            "modifiers": self.modifiers,
            "button": self.button,
            "clickCount": self.click_count,
            "force": self.force,
            "tangentialPressure": self.tangential_pressure,
            "tiltX": self.tilt_x,
            "tiltY": self.tilt_y,
            "twist": self.twist,
            "deltaX": self.delta_x,
            "deltaY": self.delta_y,
            "pointerType": self.pointer_type
        }
        if self.timestamp:
            _json["timestamp"] = self.timestamp
        if self.buttons:
            _json["buttons"] = self.buttons
        return [self._command, _json]


class BasePointer:
    def __init__(self, driver, pointer_type: str = PointerType.MOUSE):
        self.pointer_type = pointer_type
        self._driver = driver

    async def dispatch(self, event: PointerEvent):
        """dispatches a PointerEVent"""
        await self._driver.execute_cdp_cmd(*event.to_json())

    async def down(self, **kwargs):
        """press the mouse

        :param kwargs: kwargs for :class:`PointerEvent <selenium_driverless.input.pointer.PointerEvent>`
        """
        event = PointerEvent(type_=EventType.PRESS, **kwargs)
        await self.dispatch(event)

    async def up(self, **kwargs):
        """release the mouse

        :param kwargs: kwargs for :class:`PointerEvent <selenium_driverless.input.pointer.PointerEvent>`
        """
        event = PointerEvent(type_=EventType.RELEASE, **kwargs)
        await self.dispatch(event)

    async def click(self, x: float, y: float, timeout: float = None, **kwargs):
        """click

        :param x: the x coordinate
        :param y: the y coordinate
        :param timeout: the time to sleep between mouseUp & mouseDown
        :param kwargs: kwargs for :class:`PointerEvent <selenium_driverless.input.pointer.PointerEvent>`
        """
        if not timeout:
            timeout = make_rand_click_timeout()
        await self.down(click_count=1, x=x, y=y, **kwargs)
        await asyncio.sleep(timeout)
        await self.up(click_count=1, x=x, y=y, **kwargs)

    async def double_click(self, x: float, y: float, timeout: float = None, **kwargs):
        """double-click

        :param x: the x coordinate
        :param y: the y coordinate
        :param timeout: the time to sleep between mouseUp & mouseDown
        :param kwargs: kwargs for :class:`PointerEvent <selenium_driverless.input.pointer.PointerEvent>`
        """
        if not timeout:
            timeout = make_rand_click_timeout()
        await self.click(timeout=timeout, x=x, y=y, **kwargs)
        await asyncio.sleep(timeout)
        await self.down(click_count=2, x=x, y=y, **kwargs)
        await asyncio.sleep(timeout)
        await self.up(click_count=2, x=x, y=y, **kwargs)

    async def move_to(self, x: int, y: int, **kwargs):
        """dispatch a move event

        :param x: the x coordinate
        :param y: the y coordinate
        :param kwargs: kwargs for :class:`PointerEvent <selenium_driverless.input.pointer.PointerEvent>`
        """
        event = PointerEvent(type_=EventType.MOVE, x=x, y=y, **kwargs)
        await self.dispatch(event)

    async def move_path(self, total_time: float, pos_from_time_callback: typing.Callable[[float],typing.Union[typing.Tuple[int], typing.Awaitable[typing.Tuple[int]]]], freq_assumption: float = 60,
                        **kwargs):
        """
        move a path

        :param total_time: total time the pointer should take to move the path
        :param freq_assumption: assumption on a mousemove event frequency, required for accuracy
        :param kwargs: kwargs for :class:`PointerEvent <selenium_driverless.input.pointer.PointerEvent>`
        :param pos_from_time_callback: a function which returns coordinates for a specific time
        """
        x = None
        y = None
        i = -1
        start = None
        while True:
            if i == -1:
                _time = 0
            else:
                _time = time.perf_counter() - start

            if _time > total_time or _time < 0:
                return x, y

            # get coordinates at time
            res = pos_from_time_callback(_time)
            if inspect.iscoroutinefunction(pos_from_time_callback):
                await res
            x, y = res

            await self.move_to(x=x, y=y, **kwargs)

            if i == -1:
                start = time.perf_counter() - (1 / freq_assumption)  # => approximately 0.017, assuming 60 Hz
            i += 1


class Pointer:
    def __init__(self, target, pointer_type: str = PointerType.MOUSE):
        self.pointer_type = pointer_type
        self._target = target
        self.base = BasePointer(driver=target, pointer_type=pointer_type)
        self.location = [100, 0]
        self._loop = None

    async def down(self, **kwargs):
        """press the mouse

        :param kwargs: kwargs for :class:`PointerEvent <selenium_driverless.input.pointer.PointerEvent>`
        """
        await self.base.down(**kwargs)

    async def up(self, **kwargs):
        """release the mouse

        :param kwargs: kwargs for :class:`PointerEvent <selenium_driverless.input.pointer.PointerEvent>`
        """
        await self.base.up(**kwargs)

    async def click(self, x_or_elem: typing.Union[float, None]=None, y: float or None = None, move_to: bool = True,
                    move_kwargs: dict or None = None, click_kwargs: dict or None = None):
        """click

        :param x_or_elem: either the x-coordinate, or a :class:`WebElement <selenium_driverless.input.types.webelement.WebElement>`
        :param y: the y-coordinate to click at
        :param move_to: whether to move the pointer (recommended)
        :param move_kwargs: kwargs for :func:`Pointer.move_to <selenium_driverless.input.pointer.Pointer.move_to>`
        :param click_kwargs: kwargs for :func:`BasePointer.click <selenium_driverless.input.pointer.BasePointer.click>`
        """
        from selenium_driverless.types.webelement import WebElement
        if click_kwargs is None:
            click_kwargs = dict()
        if move_kwargs is None:
            move_kwargs = dict()

        if isinstance(x_or_elem, WebElement):
            x, y = await x_or_elem.mid_location()
        else:
            x = x_or_elem
        if x is None:
            x, y = self.location
        if move_to:
            await self.move_to(x, y=y, **move_kwargs)
        await self.base.click(x, y, **click_kwargs)

    async def move_to(self, x_or_elem: int=None, y: int or None = None, total_time: float = 0.5, accel: float = 2,
                      mid_time: float = None, smooth_soft=20, **kwargs):
        """move pinter to location

        :param x_or_elem: either the x-coordinate, or a :class:`WebElement <selenium_driverless.input.types.webelement.WebElement>`
        :param y: the y-coordinate to move to
        :param total_time: the total time, the pointer should take to move to the location
        :param accel: the acceleration & deceleration, the pointerMove should perform
        :param mid_time: the normalized position, where half of the time should be due (0-1)
        :param smooth_soft: how "curvy" the line should be
        :param kwargs: kwargs for :func:`BasePointer.move_path <selenium_driverless.input.pointer.BasePointer.move_path>`
        """
        from selenium_driverless.types.webelement import WebElement
        if not self.location == [x_or_elem, y]:
            if isinstance(x_or_elem, WebElement):
                x, y = await x_or_elem.mid_location()
            else:
                x = x_or_elem
            if x is None:
                x, y = self.location

            if not mid_time:
                mid_time = bias_0_dot_5(0.5, max_offset=0.3)

            # noinspection PyShadowingNames
            def pos_from_time_callback(time: float):
                return pos_at_time(path, total_time, time, accel, mid_time=mid_time)

            points = np.array([self.location, [x, y]])
            path = gen_combined_path(points, n_points_soft=5, smooth_soft=smooth_soft, n_points_distort=100,
                                     smooth_distort=0.4)
            await self.base.move_path(total_time=total_time, pos_from_time_callback=pos_from_time_callback, **kwargs)
            self.location = [x, y]
