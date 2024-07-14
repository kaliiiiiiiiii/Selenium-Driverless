from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.absolute()) + "/src")

import pytest
import pytest_asyncio
import typing
import socket
from selenium_driverless import webdriver

no_headless = False

try:
    socket.setdefaulttimeout(2)
    socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
    offline = False
except socket.error as ex:
    offline = True

skip_offline = pytest.mark.skipif(offline, reason="can only run online")


@pytest_asyncio.fixture
async def driver() -> typing.Generator[webdriver.Chrome, None, None]:
    async with webdriver.Chrome() as _driver:
        yield _driver


@pytest_asyncio.fixture
async def driver() -> typing.Generator[webdriver.Chrome, None, None]:
    options = webdriver.ChromeOptions()
    options.headless = not no_headless
    async with webdriver.Chrome(options=options) as _driver:
        yield _driver


def pytest_runtest_setup(item):
    if offline:
        for _ in item.iter_markers(name="skip_offline"):
            pytest.skip("Test requires being online")
