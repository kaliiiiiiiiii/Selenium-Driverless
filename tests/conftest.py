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
width = 1024
height = 720


try:
    socket.setdefaulttimeout(2)
    socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
    offline = False
except socket.error as ex:
    offline = True

skip_offline = pytest.mark.skipif(offline, reason="can only run online")


def mk_opt():
    options = webdriver.ChromeOptions()
    options.add_argument(f"--window-size={width},{height}")
    options.add_argument(f"--window-position={x},{y}")
    return options


@pytest_asyncio.fixture
async def driver() -> typing.Generator[webdriver.Chrome, None, None]:
    options = mk_opt()
    async with webdriver.Chrome(options=options) as _driver:
        await _driver.set_window_rect(x, y, width, height)
        yield _driver


@pytest_asyncio.fixture
async def h_driver() -> typing.Generator[webdriver.Chrome, None, None]:
    options = mk_opt()
    options.headless = not no_headless
    async with webdriver.Chrome(options=options) as _driver:
        await _driver.set_window_rect(x, y, width, height)
        yield _driver


@pytest.fixture
def sync_driver() -> typing.Generator[webdriver.Chrome, None, None]:
    options = mk_opt()
    with sync_webdriver.Chrome(options=options) as _driver:
        driver.set_window_rect(x, y, width, height)
        yield _driver


@pytest.fixture
def sync_h_driver() -> typing.Generator[webdriver.Chrome, None, None]:
    options = mk_opt()
    options.headless = not no_headless
    with sync_webdriver.Chrome(options=options) as _driver:
        # driver.set_window_rect(x, y, width, height)
        yield _driver


def pytest_runtest_setup(item):
    if offline:
        for _ in item.iter_markers(name="skip_offline"):
            pytest.skip("Test requires being online")
