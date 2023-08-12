# Selenium-Driverless

* use selenium __without chromedriver__
* undetected by __cloudfare__, __bet365__ and others

### Feel free to test my code!

## Getting Started

### Dependencies

* [Python >= 3.7](https://www.python.org/downloads/)
* [Chrome-Browser](https://www.google.de/chrome/) installed

### Installing

* Install [Chrome-Browser](https://www.google.de/chrome/)
* ```pip install selenium-driverless```


### Usage

#### with asyncio
```python
from selenium_driverless import webdriver
import asyncio


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get('http://nowsecure.nl#relax')
        # wait for redirected page
        await driver.wait_for_cdp(event="Page.loadEventFired", timeout=5)

        title = await driver.title
        url = await driver.current_url
        source = await driver.page_source
        print(title)


asyncio.run(main())
```

#### synchronous
asyncified, might be buggy

```python
from selenium_driverless.sync import webdriver

options = webdriver.ChromeOptions()
with webdriver.Chrome(options=options) as driver:
    driver.get('http://nowsecure.nl#relax')
    # wait for redirected page
    driver.wait_for_cdp(event="Page.loadEventFired", timeout=5)

    title = driver.title
    url = driver.current_url
    source = driver.page_source
    print(title)
```

#### use events
Note: synchronous might not work properly
```python
from selenium_driverless import webdriver
import asyncio

global driver


async def on_request(params):
    await driver.execute_cdp_cmd("Fetch.continueRequest", {"requestId": params['requestId']},
                                 disconnect_connect=False)
    print(params["request"]["url"])


async def main():
    global driver
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get('http://nowsecure.nl#relax')

        # enable Fetch, we don't want to disconnect after "Fetch.enable"
        await driver.execute_cdp_cmd("Fetch.enable", disconnect_connect=False)
        await driver.add_cdp_listener("Fetch.requestPaused", on_request)

        await driver.wait_for_cdp(event="Page.loadEventFired", timeout=5)

        await driver.remove_cdp_listener("Fetch.requestPaused", on_request)
        await driver.execute_cdp_cmd("Fetch.disable")

        print(await driver.title)


asyncio.run(main())
```

## Help

Please feel free to open an issue or fork!
note: please check the todo's below at first!

## Todo
- implementations
  - [ ] [`WebDriverWait`](https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/7)
  - [ ] [`EC`](https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/7) (expected-conditions)
  - [ ] [`driver.switch_to.frame`](https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/7) [workaround](https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/9#issuecomment-1663436234)
  - [ ] [`ActionChains`](https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/5)
      - [ ] [`TouchActions`](https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/5)
- protocoll
  - [ ] add cdp event handler
- [x] sync
  - [ ] move sync to threaded for allowing event_handlers
- [ ] remove pycdp dependency -_-

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
* [selenium_driverless/utils/find_chrome_executable](https://github.com/ultrafunkamsterdam/undetected-chromedriver/blob/1c704a71cf4f29181a59ecf19ddff32f1b4fbfc0/undetected_chromedriver/__init__.py#L844)
* [cdp-socket](https://github.com/kaliiiiiiiiii/CDP-Socket)
