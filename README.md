# Selenium-Driverless

* use selenium without chromedriver
* undetected by cloudfare and others

### Feel free to test my code!

## Getting Started

### Dependencies

* [Python >= 3.8](https://www.python.org/downloads/)
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
    options = webdriver.Options()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get('http://nowsecure.nl#relax')
        await driver.implicitly_wait(3)

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

options = webdriver.Options()
with webdriver.Chrome(options=options) as driver:
    driver.get('http://nowsecure.nl#relax')
    driver.implicitly_wait(3)
    
    title = driver.title
    url = driver.current_url
    source = driver.page_source
    print(title)
```

## Help

Please feel free to open an issue or fork!

## Todo

- [ ] page-interactions
  - [ ] find element
- protocoll
  - [ ] add cdp event handler
- [x] sync
  - [ ] move sync to threaded for allowing event_handlers

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
* [python-cdp](https://github.com/HMaker/python-cdp)
