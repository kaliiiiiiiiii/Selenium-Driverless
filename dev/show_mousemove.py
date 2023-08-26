from selenium_driverless import webdriver
from selenium_driverless.utils.utils import read
from selenium_driverless.input.pointer import Pointer
from selenium_driverless.scripts.geometry import gen_combined_path, pos_at_time, bias_0_dot_5
import asyncio
import os
import time
import numpy as np


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get("about:blank")
        p = Pointer(driver=driver)
        await driver.execute_script(script=read(os.getcwd() + "/show_mousemove.js", sel_root=False))

        click_points = np.array([[100, 500], [400, 300], [500, 50]])
        path = gen_combined_path(click_points, n_points_soft=5, smooth_soft=10, n_points_distort=100,
                                 smooth_distort=0.4)
        mid_time = bias_0_dot_5(0.5, max_offset=0.3)
        tot_time = 1
        accel = 2

        i = -1
        while True:
            if i == -1:
                _time = 0
                await p.click(x=100, y=500)
            else:
                _time = time.monotonic() - start

            try:
                x, y = pos_at_time(path, tot_time, _time, accel, mid_time=mid_time)
            except ValueError:
                # total time bigger than current
                await p.click(x=500, y=50)
                break

            await p.move_to(x=x, y=y)

            if i == -1:
                start = time.monotonic() - 0.017  # aproximately, assuming 60 Hz
            i += 1
        input("Press ENTER to exit")


asyncio.run(main())
