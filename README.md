# Selenium-Driverless (Non-commercial use only!)

[![Downloads](https://static.pepy.tech/badge/selenium-driverless)](https://pepy.tech/project/selenium-driverless) [![](https://img.shields.io/pypi/v/selenium-driverless.svg?color=3399EE)](https://pypi.org/project/selenium-driverless/)
[Documentation](https://kaliiiiiiiiii.github.io/Selenium-Driverless/#)


- Use Selenium __without chromedriver__
- Currently passes __Cloudflare__, __Bet365__, [Turnstile](https://github.com/kaliiiiiiiiii/Selenium-Driverless/tree/master/dev#bypass-turnstile), and others
- Multiple tabs simultaneously
- Multiple Incognito-contexts with individual proxy & cookies
- Async (`asyncio`) and sync (experimental) support
- Proxy-auth support (experimental, [example code](https://github.com/kaliiiiiiiiii/Selenium-Driverless/blob/dev/examples/proxy_with_auth.py))
- Network-interception ([documentation](https://kaliiiiiiiiii.github.io/Selenium-Driverless/api/Chrome/RequestInterception/))
- headless supported

### Questions? 
Feel free to join the [Driverless-Community](https://discord.com/invite/MzZZjr2ZM3) on **Discord**:)

Also, see [dev-branch](https://github.com/kaliiiiiiiiii/Selenium-Driverless/tree/dev) for the latest implementations.
<details>
<summary>dev-installation (click to expand)</summary>

```shell
pip uninstall -y selenium-driverless
pip install https://github.com/kaliiiiiiiiii/Selenium-Driverless/archive/refs/heads/dev.zip
```
</details>

### Still getting detected?
Feel free to give me a feedback! \
You're a company and looking for another solution? Maybe **[undetect.io](https://undetect.io/partner/steve)** is smth for you

#### Also, feel free to
<a href="https://www.buymeacoffee.com/kaliiii">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://www.buymeacoffee.com/assets/img/custom_images/black_img.png" />
    <source media="(prefers-color-scheme: light)" srcset="https://www.buymeacoffee.com/assets/img/custom_images/white_img.png" />
    <img alt="Star History Chart" src="https://www.buymeacoffee.com/assets/img/custom_images/black_img.png" />
  </picture>
</a>

### Dependencies

* [Python >= 3.7](https://www.python.org/downloads/)
* [Google-Chrome](https://www.google.de/chrome/) installed (Chromium not tested)

### Installing

* Install [Google-Chrome](https://www.google.de/chrome/)
* ```pip install selenium-driverless```


### Usage

### with asyncio
```python
from selenium_driverless import webdriver
from selenium_driverless.types.by import By
import asyncio


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get('http://nowsecure.nl#relax', wait_load=True)
        await driver.sleep(0.5)
        await driver.wait_for_cdp("Page.domContentEventFired", timeout=15)
        
        # wait 10s for elem to exist
        elem = await driver.find_element(By.XPATH, '/html/body/div[2]/div/main/p[2]/a', timeout=10)
        await elem.click(move_to=True)

        alert = await driver.switch_to.alert
        print(alert.text)
        await alert.accept()

        print(await driver.title)


asyncio.run(main())

```

### synchronous
asyncified, might be buggy

```python
from selenium_driverless.sync import webdriver

options = webdriver.ChromeOptions()
with webdriver.Chrome(options=options) as driver:
    driver.get('http://nowsecure.nl#relax')
    driver.sleep(0.5)
    driver.wait_for_cdp("Page.domContentEventFired", timeout=15)

    title = driver.title
    url = driver.current_url
    source = driver.page_source
    print(title)
```

### custom debugger address
```python
from selenium_driverless import webdriver

options = webdriver.ChromeOptions()
options.debugger_address = "127.0.0.1:2005"

# specify if you don't want to run remote
# options.add_argument("--remote-debugging-port=2005")

async with webdriver.Chrome(options=options) as driver:
  await driver.get('http://nowsecure.nl#relax', wait_load=True)
```

## Multiple tabs simultaneously
Note: asyncio is recommended, threading only works on independent webdriver.Chrome instances.

<details>
<summary>Example Code (Click to expand)</summary>

```python
from selenium_driverless.sync import webdriver
from selenium_driverless.utils.utils import read
from selenium_driverless import webdriver
import asyncio


async def target_1_handler(target):
    await target.get('https://abrahamjuliot.github.io/creepjs/')
    print(await target.title)


async def target_2_handler(target):
    await target.get("about:blank")
    await target.execute_script(script=read("/files/js/show_mousemove.js"))
    await target.pointer.move_to(500, 500, total_time=2)


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        target_1 = await driver.current_target
        target_2 = await driver.new_window("tab", activate=False)
        await asyncio.gather(
            target_1_handler(target_1),
            target_2_handler(target_2)
        )
        await target_1.focus()
        input("press ENTER to exit")


asyncio.run(main())
```

</details>

### Unique execution contexts
- execute `javascript` without getting detected
<details>
<summary>Example Code (Click to expand)</summary>

```python
from selenium_driverless.sync import webdriver
from selenium_driverless import webdriver
import asyncio


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        await driver.get('chrome://version')
        script = """
        const proxy = new Proxy(document.documentElement, {
          get(target, prop, receiver) {
            if(prop === "outerHTML"){
                console.log('detected access on "'+prop+'"', receiver)
                return "mocked value:)"
            }
            else{return Reflect.get(...arguments)}
          },
        });
        Object.defineProperty(document, "documentElement", {
          value: proxy
        })
        """
        await driver.execute_script(script)
        src = await driver.execute_script("return document.documentElement.outerHTML", unique_context=True)
        mocked = await driver.execute_script("return document.documentElement.outerHTML", unique_context=False)
        print(src, mocked)


asyncio.run(main())
```

</details>

### Pointer Interaction
see [@master/dev/show_mousemove.py](https://github.com/kaliiiiiiiiii/Selenium-Driverless/blob/master/dev/show_mousemove.py) for visualization

```python
pointer = await driver.current_pointer
move_kwargs = {"total_time": 0.7, "accel": 2, "smooth_soft": 20}

await pointer.move_to(100, 500)
await pointer.click(500, 50, move_kwargs=move_kwargs, move_to=True)
```
### Iframes
- switch and interact with iframes

```python
iframes = await driver.find_elements(By.TAG_NAME, "iframe")
await asyncio.sleep(0.5)
iframe_document = await iframes[0].content_document
# iframe_document.find_elements(...)
```

### use preferences
```python
from selenium_driverless import webdriver
options = webdriver.ChromeOptions()

 # recommended usage
options.update_pref("download.prompt_for_download", False)
# or
options.prefs.update({"download": {"prompt_for_download": False}})

# supported
options.add_experimental_option("prefs", {"download.prompt_for_download": False})
```

### Multiple Contexts
- different cookies for each context
- A context can have multiple windows and tabs within
- different proxy for each context
- opens as a window as incognito
<details>
<summary>Example Code (Click to expand)</summary>

```python
from selenium_driverless import webdriver
import asyncio


async def main():
    options = webdriver.ChromeOptions()
    async with webdriver.Chrome(options=options) as driver:
        context_1 = driver.current_context
        
        await driver.set_auth("username", "password", "localhost:5000")
        # proxy not supported on windows due to https://bugs.chromium.org/p/chromium/issues/detail?id=1310057
        context_2 = await driver.new_context(proxy_bypass_list=["localhost"], proxy_server="http://localhost:5000")
        
        await context_1.current_target.get("https://examle.com")
        await context_2.get("https://examle.com")
        input("press ENTER to exit:)")


asyncio.run(main())
```
</details>

#### Custom exception handling
You can implement custom exception handling as following

```python
import selenium_driverless
import sys
handler = (lambda e: print(f'Exception in event-handler:\n{e.__class__.__module__}.{e.__class__.__name__}: {e}',
                           file=sys.stderr))
sys.modules["selenium_driverless"].EXC_HANDLER = handler
sys.modules["cdp_socket"].EXC_HANDLER = handler
```

## Help

You found a bug? Feel free to open an issue:)
You've got other questions or proposials? feel free to join the [Driverless-Community](https://discord.com/invite/MzZZjr2ZM3) on **Discord** or open a discusion\
Note: **please check the todo's below at first!**

## Todo's
<details>
<summary>Click to expand</summary>

- implementations
  - [x] `WebElement`s
    - [ ] improve `mid_location` calculation
    - [ ] add `WebElement.screenshot`
  - [x] `Input`
      - [x] `Mouse`
        - [x] `mousemove`
        - [x] `click`
        - [ ] `scroll`
        - [ ] `drag&drop`
      - [x] `write`
      - [ ] `Touch`
        - [ ] `touchmove`
        - [ ] `TouchTap`
        - [ ] `scoll`
        - [ ] `pinch//zoom`
      - [ ] `KeyBoard`
        - [ ] `SendKeys`
          - [ ] `send files`
  - [ ] [support `options.add_extension()`](https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/37)
  - [ ] [support prefs](https://github.com/kaliiiiiiiiii/Selenium-Driverless/discussions/92#discussioncomment-7462309)
- [x] sync
  - [ ] move sync to threaded for allowing event_handlers
  - [ ] support multithreading with sync version
    - [x] on independent driver instances
    - [ ] on same driver instance
- [ ] check [Python 3.12.0](https://www.python.org/downloads/release/python-3120/)
</details>

## Authors

Copyright and Author: \
[Aurin Aegerter](mailto:aurinliun@gmx.ch) (aka **Steve**)

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
* [jsobject](https://pypi.org/project/jsobject/)
* [pycdp/browser.py](https://github.com/HMaker/python-cdp/blob/master/pycdp/browser.py)
