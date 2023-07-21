# Chromewhip - Google Chrome™ as a web service

[![Build Status](https://travis-ci.org/chuckus/chromewhip.svg?branch=master)](https://travis-ci.org/chuckus/chromewhip)
[![Docker Hub Status](https://img.shields.io/docker/build/chuckus/chromewhip.svg)](https://img.shields.io/docker/build/chuckus/chromewhip.svg)
[![PyPi version](https://img.shields.io/pypi/v/chromewhip.svg)](https://img.shields.io/pypi/v/chromewhip.svg)


### Chrome browser as an HTTP service with an splash compatible HTTP API

Chromewhip is an easily deployable service that runs headless Chrome process 
wrapped with an HTTP API. Inspired by the [`splash`](https://github.com/scrapinghub/splash) 
project, we aim to provide a drop-in replacement for the `splash` service by adhering to their documented API.

It is currently in early **alpha** and still being heavily developed. Please use the issue tracker 
to track the progress towards **beta**. For now, the required milestone can be summarised as 
**implementing the entire Splash API**.

## How to use as a service

One can simply deploy as a Docker container and use the API that is served on port `8080`.

```
docker run --init -it --rm --shm-size=1024m -p=127.0.0.1:8080:8080 --cap-add=SYS_ADMIN \
  chuckus/chromewhip
```

Refer to the HTTP API reference at the bottom of the README for what features are available.

## How to use the low-level driver

As part of the Chromewhip service, a Python 3.6 asyncio compatible driver for Chrome devtools protocol was 
developed and can be leveraged without having to run the HTTP server. The advantages of 
our devtools driver are:

* Typed Python bindings for devtools protocol through templated generation - get autocomplete with your code editor.
* Can bind events to concurrent commands, which is required for providing a robust HTTP service.

### Prerequisites

Before executing the code below, please have the following:

* Google Chrome Canary running with flag `--remote-debugging-port=9222`

### Example driver code

```python
import asyncio
import logging

from chromewhip import Chrome
from chromewhip.protocol import browser, page, dom

# see logging from chromewhip
logging.basicConfig(level=logging.DEBUG)

HOST = '127.0.0.1'
PORT = 9222

loop = asyncio.get_event_loop()
c = Chrome(host=HOST, port=PORT)

loop.run_until_complete(c.connect())

    
# use the startup tab or create a new one
tab = c.tabs[0]
tab = loop.run_until_complete(c.create_tab())

loop.run_until_complete(tab.enable_page_events())

def sync_cmd(*args, **kwargs):
    return loop.run_until_complete(tab.send_command(*args, **kwargs))
    
# send_command will return once the frameStoppedLoading event is received THAT matches
# the frameId that it is in the returned command payload.
result = sync_cmd(page.Page.navigate(url='http://nzherald.co.nz'), 
                  await_on_event_type=page.FrameStoppedLoadingEvent)

# send_command always returns a dict with keys `ack` and `event`
# `ack` contains the payload on response of a command
# `event` contains the payload of the awaited event if `await_on_event_type` is provided
ack = result['ack']['result']
event = result['event']
assert ack['frameId'] == event.frameId

sync_cmd(page.Page.setDeviceMetricsOverride(width=800,
                                            height=600,
                                            deviceScaleFactor=0.0,
                                            mobile=False))


result = sync_cmd(dom.DOM.getDocument())

dom_obj = result['ack']['result']['root']

# Python types are determined by the `types` fields in the JSON reference for the
# devtools protocol, and `send_command` will convert if possible.
assert isinstance(dom_obj, dom.Node)

print(dom_obj.nodeId)
print(dom_obj.nodeName)

# close the tab
loop.run_until_complete(c.close_tab(tab))

# or close the browser via Devtools API
tab = c.tabs[0]
sync_cmd(browser.Browser.close())
```



## Implemented HTTP API

### /render.html

Query params:

* url : string : required
  * The url to render (required)

* js : string : optional
  Javascript profile name.
  
* js_source : string : optional
   * JavaScript code to be executed in page context

* viewport : string : optional
  * View width and height (in pixels) of the browser viewport to render the web
    page. Format is "<width>x<height>", e.g. 800x600.  Default value is 1024x768.

    'viewport' parameter is more important for PNG and JPEG rendering; it is supported for
    all rendering endpoints because javascript code execution can depend on
    viewport size. 
 
### /render.png

Query params (including render.html):

* render_all : int : optional
  * Possible values are `1` and `0`.  When `render_all=1`, extend the
    viewport to include the whole webpage (possibly very tall) before rendering.
   
### Why not just use Selenium?
* chromewhip uses the devtools protocol instead of the json wire protocol, where the devtools protocol has 
greater flexibility, especially when it comes to subscribing to granular events from the browser.

## Bug reports and requests
Please simply file one using the Github tracker

## Contributing
Please :)

### How to regenerate the Python protocol files

In `scripts`, you can run `regenerate_protocol.sh`, which downloads HEAD of offical devtools specs, regenerates, 
runs some sanity tests and creates a commit with the message of official devtools specs HEAD.

From time to time, it will fail, due to desynchronization of the `chromewhip` patch with the json specs, or 
mistakes in the protocol.

Under `data`, there are `*_patch` files, which follow the [RFC 6902 JSON Patch notation](https://tools.ietf.org/html/rfc6902). 
You will see that there are some checks to see whether particular items in arrays exist before patching. If you get 
a `jsonpatch.JsonPatchTestFailed` exception, it's likely to desynchronization, so check the official spec and adjust 
the patch json file.

## Implementation

Developed to run on Python 3.6, it leverages both `aiohttp` and `asyncio` for the implementation of the 
asynchronous HTTP server that wraps `chrome`.

 
