from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent.absolute())+"/src")

import asyncio
import pytest
import typing
from selenium_driverless import webdriver
from selenium_driverless.types.target import Target

no_headless = True
max_tabs = 10
max_drivers = 3

full_driver: webdriver.Chrome = None
headless_driver: webdriver.Chrome = None
count = 0
headless_count = 0
close_lock = asyncio.Lock()

tab_sema = asyncio.Semaphore(max_tabs)
driver_sema = asyncio.Semaphore(max_tabs)


@pytest.fixture
async def driver() -> typing.Generator[webdriver.Chrome, None, None]:
    async with driver_sema:
        async with webdriver.Chrome() as _driver:
            yield _driver


@pytest.fixture
async def h_driver() -> typing.Generator[webdriver.Chrome, None, None]:
    async with driver_sema:
        options = webdriver.ChromeOptions()
        options.headless = not no_headless
        async with webdriver.Chrome(options=options) as _driver:
            yield _driver


@pytest.fixture
async def tab() -> typing.Generator[Target, None, None]:
    async with tab_sema:
        global full_driver
        global count
        if count == 0:
            full_driver = await webdriver.Chrome().__aenter__()
        tab = await full_driver.new_window()
        count += 1
        try:
            yield tab
        finally:
            async with close_lock:
                if count == 1:
                    await full_driver.quit()
                count -= 1
            await tab.close()


@pytest.fixture
async def h_tab() -> typing.Generator[Target, None, None]:
    async with tab_sema:
        global headless_driver
        global headless_count
        if headless_count == 0:
            options = webdriver.ChromeOptions()
            options.headless = not no_headless
            headless_driver = await webdriver.Chrome(options=options).__aenter__()
        tab: Target = await headless_driver.new_window()
        headless_count += 1
        try:
            yield tab
        finally:
            async with close_lock:
                if headless_count == 1:
                    await headless_driver.quit()
                headless_count -= 1
            await tab.close()
