# Selenium-Driverless

* 

### Feel free to test my code!

## Getting Started

### Dependencies

* [Python >= 3.8](https://www.python.org/downloads/)
* [Chrome-Browser](https://www.google.de/chrome/) installed

### Installing

* [Windows] Install [Chrome-Browser](https://www.google.de/chrome/)
* ```pip install selenium_interceptor```


### Usage

#### example script
```python
import asyncio
from pycdp import cdp
from pycdp.browser import ChromeLauncher
from pycdp.asyncio import connect_cdp
from selenium_driverless.utils.utils import find_chrome_executable


async def main():
    PORT = 9222
    chrome = ChromeLauncher(
        binary=find_chrome_executable(),
        args=[f'--remote-debugging-port={PORT}']
    )
    # ChromeLauncher.launch() is blocking, run it on a background thread
    await asyncio.get_running_loop().run_in_executor(None, chrome.launch)
    conn = await connect_cdp(f'http://localhost:{PORT}')
    target_id = await conn.execute(cdp.target.create_target('about:blank'))
    target_session = await conn.connect_session(target_id)
    await target_session.execute(cdp.page.enable())
    # you may use "async for target_session.listen()" to listen multiple events, here we listen just a single event.
    with target_session.safe_wait_for(cdp.page.DomContentEventFired) as navigation:
        await target_session.execute(cdp.page.navigate('http://nowsecure.nl#relax'))
        await navigation
        
    await target_session.execute(cdp.page.close())
    await conn.close()
    await asyncio.get_running_loop().run_in_executor(None, chrome.kill)


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
