# Selenium-Driverless

* 

### Feel free to test my code!

## Getting Started

### Dependencies

* [Python >= 3.7](https://www.python.org/downloads/)
* [Chrome-Browser](https://www.google.de/chrome/) installed

### Installing

* [Windows] Install [Chrome-Browser](https://www.google.de/chrome/)
* ```pip install selenium_interceptor```


### Usage

#### example script
```python
import asyncio
import logging
import subprocess

from selenium_driverless.async_ import Chrome
from selenium_driverless.async_.protocol import browser, page
from selenium_driverless.utils.utils import find_chrome_executable

# see logging from Driverless
logging.basicConfig(level=logging.DEBUG)


async def main():
    HOST = '127.0.0.1'
    PORT = 9222
    subprocess.Popen([find_chrome_executable(), f"--remote-debugging-port={PORT}"])
    c = Chrome(host=HOST, port=PORT)

    await c.connect()
    tab = c.tabs[0]
    await tab.enable_page_events()

    await tab.send_command(page.Page.navigate(url='http://nowsecure.nl#relax'),
                           await_on_event_type=page.FrameStartedLoadingEvent)

    await tab.send_command(browser.Browser.close())


if __name__ == "__main__":
    asyncio.run(main())

```

## Help

Please feel free to open an issue or fork!

## Todo



## Deprecated

## Authors

[Aurin Aegerter](mailto:aurinliun@gmx.ch)

## License

Shield: [![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

Unless specified differently in a single file, this work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg

## Disclaimer

I am not responsible what you use the code for!!! Also no warranty!

## Acknowledgments

Inspiration, code snippets, etc.
* [Chromewhip](https://github.com/chazkii/chromewhip)
* [selenium_driverless/utils/find_chrome_executable](https://github.com/ultrafunkamsterdam/undetected-chromedriver/blob/1c704a71cf4f29181a59ecf19ddff32f1b4fbfc0/undetected_chromedriver/__init__.py#L844)
