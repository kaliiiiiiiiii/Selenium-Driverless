import asyncio
import time
import inspect


class Modifiers:
    NONE = 0
    ALT = 1
    CTRL = 2
    COMMAND = 4
    SHIFT = 8


class PointerType:
    MOUSE = "mouse"
    PEN = "pen"


class MouseButton:
    NONE = "none"
    LEFT = "left"
    MIDDLE = "middle"
    RIGHT = "right"
    BACK = "back"
    FORWARD = "forward"


class Buttons:
    NONE = 0
    LEFT = 1
    RIGHT = 2
    MIDDLE = 4
    BACK = 8
    FORWARD = 16
    DEFAULT = None


class EventType:
    PRESS = "mousePressed"
    RELEASE = "mouseReleased"
    MOVE = "mouseMoved"
    WHEEL = "mouseWheel"


class PointerEvent:
    def __init__(self, type_: str, x: int, y: int,
                 modifiers: int = Modifiers.NONE,
                 timestamp: float = None, button: str = MouseButton.LEFT, buttons: int = Buttons.DEFAULT,
                 click_count: int = 0, force: float = 0, tangential_pressure: float = 0,
                 tilt_x: float = 0, tilt_y: float = 0, twist: float = 0, delta_x: int = 0, delta_y: int = 0,
                 pointer_type: str = PointerType.MOUSE):
        """
        see https://chromedevtools.github.io/devtools-protocol/tot/Input/#method-dispatchMouseEvent for documentation
        Args:
        type_: str,
        x: int, y: int,
        modifiers: int = Modifiers.NONE,
        timestamp: float = None,
        button: str = MouseButton.NONE,
        buttons: int = None,
        click_count: int = 0,
        force: float = 0,
        tangential_pressure: float = 0,
        tilt_x: float = 0, tilt_y: float = 0,
        twist: float = 0,
        delta_x: int = 0, delta_y: int = 0,
        pointer_type: str = PointerType.MOUSE
        """
        self._comand = "Input.dispatchMouseEvent"

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

    def to_json(self):
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
        return [self._comand, _json]


class BasePointer:
    def __init__(self, driver, pointer_type: str = PointerType.MOUSE):
        self.pointer_type = pointer_type
        self._driver = driver

    async def dispatch(self, event: PointerEvent):
        await self._driver.execute_cdp_cmd(*event.to_json())

    async def down(self, **kwargs):
        event = PointerEvent(type_=EventType.PRESS, **kwargs)
        await self.dispatch(event)

    async def up(self, **kwargs):
        event = PointerEvent(type_=EventType.RELEASE, **kwargs)
        await self.dispatch(event)

    async def click(self, timeout: float = 0.25, **kwargs):
        await self.down(click_count=1, **kwargs)
        await asyncio.sleep(timeout)
        await self.up(click_count=1, **kwargs, )

    async def doubble_click(self, timeout: float = 0.25, **kwargs):
        await self.click(timeout=timeout, **kwargs)
        await asyncio.sleep(timeout)
        await self.down(click_count=2, **kwargs)
        await asyncio.sleep(timeout)
        await self.up(click_count=2, **kwargs)

    async def move_to(self, **kwargs):
        event = PointerEvent(type_=EventType.MOVE, **kwargs)
        await self.dispatch(event)

    async def move_path(self, total_time: float, pos_from_time_callback: callable, freq_assumpton: float = 60):
        """
        param: total_time
            total time the pointer shoul take to move the path
        param: pos_from_time_callback
            a function which returns cordinates for a specific time
            def callback(time:float):
                # do something
                return [x, y]
        param freq_assumption:
            assumption on mousemove event frequency, required for accuracy
        """
        x = None
        y = None
        i = -1
        start = None
        while True:
            if i == -1:
                _time = 0
            else:
                _time = time.monotonic() - start

            if _time > total_time or _time < 0:
                return x, y

            # get cordinates at time
            res = pos_from_time_callback(_time)
            if inspect.iscoroutinefunction(pos_from_time_callback):
                await res
            x, y = res

            await self.move_to(x=x, y=y)

            if i == -1:
                start = time.monotonic() - (1/freq_assumpton)  # => aproximately 0.017, assuming 60 Hz
            i += 1
