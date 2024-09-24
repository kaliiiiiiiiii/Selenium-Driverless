from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.absolute()) + "/src")

import pytest
import pytest_asyncio
import typing
import socket
from selenium_driverless import webdriver
from selenium_driverless.sync import webdriver as sync_webdriver

no_headless = False
x = y = 30
h_x = h_y = -2400  # https://issues.chromium.org/issues/367764867
width = 1024
height = 720


if no_headless:
    # noinspection PyRedeclaration
    h_x, h_y = x, y

try:
    socket.setdefaulttimeout(2)
    socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
    offline = False
except socket.error as ex:
    offline = True

skip_offline = pytest.mark.skipif(offline, reason="can only run online")


def mk_opt(headless=False):
    options = webdriver.ChromeOptions()
    options.add_argument(f"--window-size={width},{height}")
    if headless and not no_headless:
        _x, _y = h_x, h_y
    else:
        _x, _y = x, y
    options.add_argument(f"--window-position={_x},{_y}")
    return options


@pytest_asyncio.fixture
async def driver() -> typing.Generator[webdriver.Chrome, None, None]:
    options = mk_opt()
    debug = False
    # options.add_argument("--log-level=0")
    async with webdriver.Chrome(options=options, debug=debug) as _driver:
        await _driver.set_window_rect(x, y, width, height)
        yield _driver


@pytest_asyncio.fixture
async def h_driver() -> typing.Generator[webdriver.Chrome, None, None]:
    options = mk_opt(headless=True)
    options.headless = not no_headless
    async with webdriver.Chrome(options=options) as _driver:
        await _driver.set_window_rect(h_x, h_y, width, height)
        yield _driver


@pytest.fixture
def sync_driver() -> typing.Generator[webdriver.Chrome, None, None]:
    options = mk_opt()
    with sync_webdriver.Chrome(options=options) as _driver:
        driver.set_window_rect(x, y, width, height)
        yield _driver


@pytest.fixture
def sync_h_driver() -> typing.Generator[webdriver.Chrome, None, None]:
    options = mk_opt(headless=True)
    options.headless = not no_headless
    with sync_webdriver.Chrome(options=options) as _driver:
        _driver.set_window_rect(h_x, h_y, width, height)
        yield _driver


def pytest_runtest_setup(item):
    if offline:
        for _ in item.iter_markers(name="skip_offline"):
            pytest.skip("Test requires being online")
