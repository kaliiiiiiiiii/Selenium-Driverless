# Licensed to the Software Freedom Conservancy (SFC) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The SFC licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# modified by kaliiiiiiiiii | Aurin Aegerter
# all modifications are licensed under the license provided at LICENSE.md

from __future__ import annotations

import asyncio
import time
import warnings
import numpy as np
import typing
import aiofiles

from base64 import b64decode
from collections import defaultdict
from cdp_socket.exceptions import CDPError

# driverless
from selenium_driverless.types.by import By
from selenium_driverless.types.deserialize import JSRemoteObj, StaleJSRemoteObjReference
from selenium_driverless.scripts.geometry import rand_mid_loc, overlap, is_point_in_polygon


class NoSuchElementException(Exception):
    pass


class StaleElementReferenceException(StaleJSRemoteObjReference):
    def __init__(self, elem):
        elem._stale = True
        message = f"Page or Frame has been reloaded, or the element removed, {elem}"
        super().__init__(_object=elem, message=message)


class ElementNotVisible(Exception):
    pass


class ElementNotInteractable(Exception):
    def __init__(self, x: float, y: float, _type: str = "interactable"):
        super().__init__(f"element not {_type} at x:{x}, y:{y}, it might be hidden under another one")


class ElementNotClickable(ElementNotInteractable):
    def __init__(self, x: float, y: float):
        super().__init__(x, y, _type="clickable")


# noinspection PyProtectedMember
class WebElement(JSRemoteObj):
    """Represents a DOM element.

    Generally, all interesting operations that interact with a document will be
    performed through this interface.

    All method calls will do a freshness check to ensure that the element
    reference is still valid.  This essentially determines whether the
    element is still attached to the DOM.  If this test fails, then a
    ``StaleElementReferenceException`` is thrown, and all future calls to this
    instance will fail.
    """

    def __init__(self, target, frame_id: int or None, isolated_exec_id: int or None, obj_id=None,
                 node_id=None, backend_node_id: str = None, loop=None, class_name: str = None,
                 context_id: int = None, is_iframe: bool = False) -> None:
        self._loop = loop
        # {'type': 'node', 'weakLocalObjectReference': 1}
        #if not (obj_id or node_id or backend_node_id):
        #    raise ValueError("either js, obj_id or node_id need to be specified")
        self._node_id = node_id
        self._backend_node_id = backend_node_id
        self._class_name = class_name
        self._started = False
        self.___context_id__ = context_id
        self._obj_ids = {context_id: obj_id}
        self.___frame_id__ = None
        self._is_iframe = is_iframe
        self._stale = False
        if obj_id and context_id:
            self._obj_ids[context_id] = obj_id
        self.___obj_id__ = None
        super().__init__(target=target, frame_id=frame_id, obj_id=obj_id, isolated_exec_id=isolated_exec_id)

    def __await__(self):
        return self.__aenter__().__await__()

    async def __aenter__(self):
        if not self._started:
            if not self.__target__._page_enabled:
                await self.__target__.execute_cdp_cmd("Page.enable")
            self._started = True

        return self

    @property
    async def obj_id(self) -> str:
        """**async** returns the `Runtime.RemoteObjectId <https://vanilla.aslushnikov.com/?Runtime.RemoteObjectId>`_ for the element
        """
        return await self.__obj_id_for_context__()

    @property
    async def context_id(self):
        """
        **async** the ``Runtime.ExecutionContextId``
        """
        self._check_stale()
        if not self.___context_id__:
            await self.obj_id
        return self.__context_id__

    def _check_stale(self):
        if self._stale:
            raise StaleElementReferenceException(elem=self)

    @property
    def _args_builder(self) -> dict:
        self._check_stale()
        if self._node_id:
            return {"nodeId": self._node_id}
        elif self.__obj_id__:
            return {"objectId": self.__obj_id__}
        elif self._backend_node_id:
            return {"backendNodeId": self._backend_node_id}
        else:
            raise ValueError(f"missing remote element id's for {self}")

    async def __obj_id_for_context__(self, context_id: int = None):
        self._check_stale()
        if not self._obj_ids.get(context_id):
            args = {}
            if self._backend_node_id:
                args["backendNodeId"] = self._backend_node_id
            elif self._node_id:
                args["nodeId"] = self._node_id
            else:
                raise ValueError(f"missing remote element id's for {self}")

            if context_id:
                args["executionContextId"] = context_id
            try:
                res = await self.__target__.execute_cdp_cmd("DOM.resolveNode", args)
            except CDPError as e:
                if e.code == -32000 and 'No node with given id found' in e.message:
                    raise StaleElementReferenceException(self)
                else:
                    raise e
            obj_id = res["object"].get("objectId")
            if obj_id:
                if self.__context_id__ == context_id:
                    self.___obj_id__ = obj_id
                self._obj_ids[context_id] = obj_id
            class_name = res["object"].get("className")
            if class_name:
                self._class_name = class_name
        return self._obj_ids.get(context_id)

    @property
    def __context_id__(self):
        if self.__obj_id__:
            return int(self.__obj_id__.split(".")[1])
        else:
            return self.___context_id__

    @property
    async def node_id(self):
        """
        **async**
        the ``DOM.NodeId``
        """
        self._check_stale()
        if not self._node_id:
            node = await self.__target__.execute_cdp_cmd("DOM.requestNode", {"objectId": await self.obj_id})
            self._node_id = node["nodeId"]
        return self._node_id

    @property
    async def __frame_id__(self) -> int:
        if not self.___frame_id__:
            await self._describe()
        return self.___frame_id__

    @property
    async def content_document(self) -> WebElement:
        """
        **async** gets the contentDocument element of the iframe (or frame). Returns None if this isn't an iframe.
        """
        _desc = await self._describe()
        if _desc.get("localName") in ["iframe", "frame"]:
            node = _desc.get("contentDocument")
            if node:
                frame_id = _desc.get("frameId")
                if node['documentURL'] == 'about:blank':
                    # wait for frame to load
                    if not self.__target__._page_enabled:
                        await self.__target__.execute_cdp_cmd("Page.enable")
                    async for data in await self.__target__.get_cdp_event_iter("Page.frameNavigated"):
                        frame = data["frame"]
                        if frame["id"] == frame_id:
                            break
                    self._stale = False
                    _desc = await self._describe()
                    node = _desc.get("contentDocument")
                if self._loop:
                    from selenium_driverless.sync.webelement import WebElement as SyncWebElement
                    return await SyncWebElement(backend_node_id=node.get('backendNodeId'),
                                                target=self.__target__, loop=self._loop,
                                                class_name='HTMLIFrameElement',
                                                isolated_exec_id=None, frame_id=frame_id)
                else:
                    return await WebElement(backend_node_id=node.get('backendNodeId'),
                                            target=self.__target__, loop=self._loop,
                                            class_name='HTMLIFrameElement',
                                            isolated_exec_id=None, frame_id=frame_id)

            # different target for cross-site
            targets = await self.__target__.get_targets_for_iframes([self])
            if targets:
                return await targets[0]._document_elem

    @property
    async def shadow_roots(self) -> typing.List[WebElement]:
        """
        **async** gets a list of currently connected shadow root documents
        """
        isolated_exec_id = await self.__isolated_exec_id__
        _desc = await self._describe()
        res = []
        shadow_roots = _desc.get("shadowRoots", [])
        for node in shadow_roots:
            frame_id = _desc.get("frameId")
            state = node.get('shadowRootType')

            if self._loop:
                from selenium_driverless.sync.webelement import WebElement as SyncWebElement
                elem = await SyncWebElement(backend_node_id=node.get('backendNodeId'),
                                            target=self.__target__, loop=self._loop,
                                            class_name=f'#document-fragment({state} shadow-root)',
                                            isolated_exec_id=isolated_exec_id, frame_id=frame_id)
            else:
                elem = await WebElement(backend_node_id=node.get('backendNodeId'),
                                        target=self.__target__, loop=self._loop,
                                        class_name=f'#document-fragment({state} shadow-root)',
                                        isolated_exec_id=isolated_exec_id, frame_id=frame_id)
            res.append(elem)
        return res

    @property
    async def shadow_root(self) -> typing.Union[WebElement, None]:
        """**async** returns the (first)  document for this element
        """
        roots = await self.shadow_roots
        if len(roots) != 0:
            return roots[0]

    @property
    async def document_url(self):
        """**async** gets the url if the element is an iframe, else returns ``None``"""
        res = await self._describe()
        return res.get('documentURL')

    @property
    async def backend_node_id(self):
        """
        **async** the ``DOM.BackendNodeId``
        """
        if not self._backend_node_id:
            await self._describe()
        return self._backend_node_id

    @property
    def class_name(self):
        """
        the ClassName of the element (if available)
        """
        return self._class_name

    async def find_element(self, by: str, value: str, idx: int = 0, timeout: float or None = None) -> WebElement:
        """find an element in the current target

        :param by: one of the locators at :func:`By <selenium_driverless.types.by.By>`
        :param value: the actual query to find the element by
        :param timeout: how long to wait for the element to exist
        :param idx: might be removed
        """
        elems = []
        start = time.perf_counter()
        while not elems:
            elems = await self.find_elements(by=by, value=value)
            if (not timeout) or (time.perf_counter() - start) > timeout:
                break
        if elems:
            if isinstance(elems, list):
                return elems[idx]
            else:
                raise Exception(
                    "find_elements returned not a list. This possibly is related to https://github.com/kaliiiiiiiiii/Selenium-Driverless/issues/84\n",
                    elems)
        raise NoSuchElementException()

    async def find_elements(self, by: str = By.ID, value: str or None = None):
        """find multiple elements in the current target

        :param by: one of the locators at :func:`By <selenium_driverless.types.by.By>`
        :param value: the actual query to find the elements by
        """
        from selenium_driverless.types.by import By

        if by == By.ID:
            by = By.XPATH
            value = f'//*[@id="{value}"]'
        elif by == By.CLASS_NAME:
            by = By.XPATH
            value = f'//*[@class="{value}"]'
        elif by == By.NAME:
            by = By.XPATH
            value = f'//*[@name="{value}"]'

        if by == By.TAG_NAME:
            return await self.execute_script("return obj.getElementsByTagName(arguments[0])",
                                             value, serialization="deep", unique_context=True, timeout=10)
        elif by == By.CSS_SELECTOR:
            return await self.execute_script("return obj.querySelectorAll(arguments[0])", value, timeout=10,
                                             unique_context=True)
        elif by == By.XPATH:
            script = """return document.evaluate(
                          arguments[0],
                          obj,
                          null,
                          XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
                          null,
                        );"""
            return await self.execute_script(script, value, serialization="deep", timeout=10, unique_context=True)
        else:
            raise ValueError("unexpected by")

    async def _describe(self):
        args = {"pierce": True}
        args.update(self._args_builder)
        res = await self.__target__.execute_cdp_cmd("DOM.describeNode", args)
        res = res["node"]
        self._backend_node_id = res["backendNodeId"]
        self._node_id = res["nodeId"]
        self.___frame_id__ = res.get("frameId")
        return res

    async def get_listeners(self, depth: int = 3):
        """
        gets all listeners on the element. see `DOMDebugger.getEventListeners <https://vanilla.aslushnikov.com/?DOMDebugger.getEventListeners>`_

        :param depth: maximum depth (nested elements) to find listeners for
        """
        res = await self.__target__.execute_cdp_cmd(
            "DOMDebugger.getEventListeners", {"objectId": await self.obj_id, "depth": depth, "pierce": True})
        return res['listeners']

    @property
    async def source(self):
        """
        **async** the OuterHtml of the element
        """
        args = self._args_builder
        try:
            res = await self.__target__.execute_cdp_cmd("DOM.getOuterHTML", args)
        except CDPError as e:
            if e.code == -32000 and e.message == 'Could not find node with given id':
                raise StaleElementReferenceException(self)
            else:
                raise e
        return res["outerHTML"]

    async def set_source(self, value: str):
        """
        sets the OuterHTML of the element

        :param value: the str to set the outerHtml to
        """
        try:
            await self.__target__.execute_cdp_cmd("DOM.setOuterHTML",
                                                  {"nodeId": await self.node_id, "outerHTML": value})
        except CDPError as e:
            if e.code == -32000 and 'Could not find node with given id' in e.message:
                raise StaleElementReferenceException(self)
            else:
                raise e

    async def get_property(self, name: str) -> str or None:
        """Gets the given property of the element.

        :param name: the name of the property to get

        .. note::
            this gets the JavaScript property (``elem[name]``), and not HTML property
        """
        return await self.execute_script(f"return obj[arguments[0]]", name)

    @property
    async def tag_name(self) -> str:
        """This element's ``tagName`` property."""
        node = await self._describe()
        return node["localName"]

    @property
    async def text(self) -> str:
        """**async** The text of the element. (``elem.textContent``)"""
        return await self.get_property("textContent")

    @property
    async def value(self) -> str:
        """**async** The value of the element. (``elem.value``)"""
        return await self.get_property("value")

    async def clear(self) -> None:
        """Clears the text if it's a text entry element. (``elem.value = ""``)
        """
        await self.execute_script("obj.value = ''", unique_context=True)

    async def remove(self):
        """
        remove the element from the page//dom//html
        """
        await self.__target__.execute_cdp_cmd("DOM.removeNode", {"nodeId": await self.node_id})

    async def highlight(self, highlight=True):
        """
        highlight the element

        :param highlight: whether to disable or enable highlight

        .. note::
            highlight automatically fades on any user-interaction, you might use a for-loop
        """
        if not self.__target__._dom_enabled:
            await self.__target__.execute_cdp_cmd("DOM.enable")
        if highlight:
            args = self._args_builder
            args["highlightConfig"] = {
                "showInfo": True,
                "borderColor": {
                    "r": 76, "g": 175, "b": 80, "a": 1
                },
                "contentColor": {
                    "r": 76, "g": 175, "b": 80,
                    "a": 0.24
                },
                "shapeColor": {
                    "r": 76, "g": 175, "b": 80,
                    "a": 0.24
                }
            }
            await self.__target__.execute_cdp_cmd("Overlay.enable")
            await self.__target__.execute_cdp_cmd("Overlay.highlightNode", args)
        else:
            await self.__target__.execute_cdp_cmd("Overlay.disable")

    async def focus(self):
        """
        focuses the element (``Dom.focus``)
        """
        args = self._args_builder
        return await self.__target__.execute_cdp_cmd("DOM.focus", args)

    # noinspection PyIncorrectDocstring
    async def is_clickable(self, listener_depth=3, box_model: dict = None):
        """
        returns ``True`` if the element type is one of "a", "button", "command", "details", "input", "select", "textarea", "video", "map"
        otherwise checks for "click", "mousedown" or "mouseup" event listeners on the element

        :param listener_depth: the depth (nested elements) to get event-listeners for
        """
        if box_model is None:
            try:
                box_model = await self.box_model
            except ElementNotVisible:
                return False
        if not await self.is_visible(box_model=box_model):
            return False
        _type = await self.tag_name
        if _type in ["a", "button", "command", "details", "input", "select", "textarea", "video", "map"]:
            return True
        is_clickable: bool = listener_depth is None
        if not is_clickable:
            listeners = await self.get_listeners(depth=listener_depth)
            for listener in listeners:
                _type = listener["type"]
                if _type in ["click", "mousedown", "mouseup"]:
                    is_clickable = True
                    break
        return is_clickable

    async def move_to(self, timeout: float = None, visible_timeout: float = 10, spread_a: float = 1,
                      spread_b: float = 1,
                      bias_a: float = 0.5, bias_b: float = 0.5, border: float = 0.05, scroll_to=True,
                      box_model: dict = None) -> None:
        """
        moves the mouse to the element
        see :func:`Elem.send_keys <selenium_driverless.types.webelement.WebElement.click> for details or the arguments`
        """
        if scroll_to:
            await self.scroll_to()
        cords = None
        start = time.perf_counter()
        while not cords:
            try:
                if box_model is None:
                    box_model = await self.box_model
                cords = await self.mid_location(spread_a, spread_b, bias_a, bias_b, border, box_model=box_model)
            except ElementNotVisible:
                await asyncio.sleep(0.05)
            if (time.perf_counter() - start) > visible_timeout:
                raise asyncio.TimeoutError(f"Couldn't compute element location within {visible_timeout} seconds")
        x, y = cords
        await self.__target__.pointer.move_to(x, y=y, total_time=timeout)

    # noinspection PyIncorrectDocstring
    async def click(self, timeout: float = None, visible_timeout: float = 10, spread_a: float = 1, spread_b: float = 1,
                    bias_a: float = 0.5, bias_b: float = 0.5, border: float = 0.05, scroll_to=True,
                    move_to: bool = True,
                    ensure_clickable: typing.Union[bool, int] = False, box_model: dict = None) -> None:
        """Clicks the element.

        :param timeout: the time in seconds to take for clicking on the element
        :param visible_timeout: the time in seconds to wait for the element to be at least partially visible
        :param spread_a: spread over a
        :param spread_b: spread over b
        :param bias_a: bias over a (0-1)
        :param bias_b: bias over b (0-1)
        :param border: minimum border towards element edges (relative to element => 1).
            Random generated points outside that border get re-generated.
        :param scroll_to: whether to scroll to the element
        :param move_to: whether to move the mouse to the element
        :param ensure_clickable: whether to ensure that the element is clickable.

        .. note::
            a spread of 1 is equivalent to 6 std.
            relative to the element.
            (=> 99.7 %)
        """
        if scroll_to:
            await self.scroll_to()
        cords = None
        start = time.perf_counter()
        while not cords:
            try:
                if box_model is None:
                    box_model = await self.box_model
                cords = await self.mid_location(spread_a, spread_b, bias_a, bias_b, border, box_model=box_model)
            except ElementNotVisible:
                await asyncio.sleep(0.05)
            if (time.perf_counter() - start) > visible_timeout:
                raise asyncio.TimeoutError(f"Couldn't compute element location within {visible_timeout} seconds")
        x, y = cords
        if ensure_clickable:
            is_clickable = await self.is_clickable(box_model=box_model)
            if not is_clickable:
                raise ElementNotClickable(x, y)

        await self.__target__.pointer.click(x, y=y, click_kwargs={"timeout": timeout}, move_to=move_to)

    async def write(self, text: str, click_kwargs=None, click_on: bool = True):
        """
        inserts literal text to the element

        .. warning::

            This method is generally detectable.
            You might consider using :func:`Elem.send_keys <selenium_driverless.types.webelement.WebElement.send_keys>` instead.

        :param text: the text to send
        :param click_kwargs: arguments to pass for :func:`Elem.send_keys <selenium_driverless.types.webelement.WebElement.send_keys>`
        :param click_on: whether to click on the element before inserting the text
        """
        if click_kwargs is None:
            click_kwargs = {}
        if click_on:
            await self.click(**click_kwargs)
        else:
            await self.focus()
        await self.__target__.execute_cdp_cmd("Input.insertText", {"text": text})

    async def set_file(self, path: str):
        """
        sets the file on the current element (has to accept files)

        :param path: the absolute path to the file
        """
        await self.set_files([path])

    async def set_files(self, paths: typing.List[str]):
        """
        sets files on the current element (has to accept files)

        :param paths: the absolute paths to the files
        """
        args = {"files": paths}
        args.update(self._args_builder)
        await self.__target__.execute_cdp_cmd("DOM.setFileInputFiles", args)

    async def send_keys(self, text: str, click_kwargs: dict = None, click_on: bool = True) -> None:
        """
        send text & keys to the target

        :param text: the text to send to the target
        :param click_kwargs: arguments to pass for :func:`Elem.click <selenium_driverless.types.webelement.WebElement.click>`
        :param click_on: whether to click on the element before sending the keys
        """
        if click_kwargs is None:
            click_kwargs = {}
        if click_on:
            await self.click(**click_kwargs)
        else:
            await self.focus()
        await self.__target__.send_keys(text)

    # noinspection PyIncorrectDocstring
    async def mid_location(self, spread_a: float = 1, spread_b: float = 1, bias_a: float = 0.5, bias_b: float = 0.5,
                           border: float = 0.05, box_model: dict = None) -> typing.List[int]:
        """
        returns random location in the element with probability close to the middle

        :param spread_a: spread over a
        :param spread_b: spread over b
        :param bias_a: bias over a (0-1)
        :param bias_b: bias over b (0-1)
        :param border: minimum border towards element edges (relative to the element => 1).
            Random generated points outside that border get re-generated.

        .. note::
            a spread of 1 is equivalent to 6 std.
            relative to the element.
            (=> 99.7 %)
        """
        loop = asyncio.get_event_loop()
        if box_model is None:
            box_model = await self.box_model
        visible, overlap_polygon = await self.p_visible(box_model=box_model)
        if not visible:
            raise ElementNotVisible("Element is not displayed")
        try:
            box = await self.box_model
        except CDPError as e:
            message = 'Could not compute box model.'
            if e.code == -32000 and message in e.message:
                raise ElementNotVisible(message)
            else:
                raise e

        layers = ["content", "padding", "border"]
        vertices = None
        point = []
        for layer in layers:
            vertices = box[layer]
            try:
                def helper(_point):
                    while (not _point) or (not is_point_in_polygon(_point, overlap_polygon)):
                        # todo: add better overlap point generation
                        _point = rand_mid_loc(vertices, spread_a, spread_b, bias_a, bias_b, border)
                    return _point

                try:
                    point = await asyncio.wait_for(loop.run_in_executor(None, lambda: helper(point)), 2)
                except asyncio.TimeoutError:
                    raise ValueError('The area of the element is 0')
            except ValueError as e:
                if e.args[0] != 'The area of the element is 0':
                    raise e
        if vertices is None:
            raise ValueError('The area of the element is 0')

        # noinspection PyUnboundLocalVariable
        x = int(point[0])
        y = int(point[1])
        return [x, y]

    async def submit(self):
        """Submits a form.

        .. warning::
            the current implementation likely is detectable. It's recommended to use click instead if possible
        """
        script = (
            "/* submitForm */var form = this;\n"
            'while (form.nodeName != "FORM" && form.parentNode) {\n'
            "  form = form.parentNode;\n"
            "}\n"
            "if (!form) { throw Error('Unable to find containing form element'); }\n"
            "if (!form.ownerDocument) { throw Error('Unable to find owning document'); }\n"
            "var e = form.ownerDocument.createEvent('Event');\n"
            "e.initEvent('submit', true, true);\n"
            "if (form.dispatchEvent(e)) { HTMLFormElement.prototype.submit.call(form) }\n"
        )
        return await self.execute_script(script, unique_context=True)

    @property
    async def dom_attributes(self) -> dict:
        """returns the dom attributes as a dict

        .. warning::

            this isn't implemented properly yet and might change,
            use :func:`WebElement.execute_script <selenium_driverless.types.webelement.WelElement.execute_script`
            instead

        """
        try:
            res = await self.__target__.execute_cdp_cmd("DOM.getAttributes", {"nodeId": await self.node_id})
            attr_list = res["attributes"]
            attributes_dict = defaultdict(lambda: None)

            for i in range(0, len(attr_list), 2):
                key = attr_list[i]
                value = attr_list[i + 1]
                attributes_dict[key] = value
            return attributes_dict
        except CDPError as e:
            if not (e.code == -32000 and 'Node is not an Element' in e.message):
                raise e

    async def get_dom_attribute(self, name: str) -> str or None:
        """Gets the given attribute of the element.
        Only returns attributes declared in the element's HTML markup.

        :param name: Name of the attribute to retrieve.

        .. warning::

            this isn't implemented properly yet and might change,
            use :func:`WebElement.execute_script <selenium_driverless.types.webelement.WelElement.execute_script`
            instead

        """
        attrs = await self.dom_attributes
        return attrs[name]

    async def set_dom_attribute(self, name: str, value: str):
        """set a dom_attribute

        :param name: the name of the DOM (=>html) attribute
        :param value: the value to set the attribute to
        """
        await self.__target__.execute_cdp_cmd("DOM.setAttributeValue", {"nodeId": await self.node_id,
                                                                        "name": name, "value": value})

    async def get_attribute(self, name):
        """Alias to WebElement.get_property.

        .. warning::

            this isn't implemented properly yet and might change,
            use :func:`WebElement.execute_script <selenium_driverless.types.webelement.WelElement.execute_script`
            instead

        """
        return await self.get_property(name)

    async def is_selected(self) -> bool:
        """Returns whether the element is selected.

        Can be used to check if a checkbox or radio button is selected.
        """
        result = await self.get_property("checked")
        if result:
            return True
        else:
            return False

    async def is_enabled(self) -> bool:
        """Returns whether the element is enabled."""
        return not await self.get_property("disabled")

    # RenderedWebElement Items
    async def p_visible(self, box_model: dict = None) -> typing.Tuple[float, typing.Union[np.ndarray, list]]:

        """
        Whether the element is visible to a user.
        This does not check the opacity, since the element might still be interactable.
        Returns the percentage (0.0 to 1.0) visible within the viewport and polygon of the area visible
        """
        visible = 0
        polygon = np.array([])
        loop = asyncio.get_event_loop()

        elem_visible, vh, vw = await self.execute_script("""
            const style = window.getComputedStyle(obj);
            const elem_visible = ((style.display !== 'none') && (style.visibility !== 'hidden'))
            const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0)
            const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0)
            return [elem_visible, vh, vw];
            """, unique_context=True, max_depth=4)

        viewport = np.array([[0, 0], [vw, 0], [vw, vh], [0, vh]])
        if elem_visible:
            if box_model is None:
                try:
                    box_model = await self.box_model
                except ElementNotVisible:
                    return visible, polygon
            visible, polygon = await loop.run_in_executor(None, lambda: overlap(viewport, box_model["border"]))

        return visible, polygon

    async def is_visible(self, box_model: dict = None, minimum_p: float = 0.0001):
        """
        returns true if the area of the element which is visible is bigger than minimum_p (0 to 1, percentage visible)

        .. note:
            This does not check opacity=0
        """
        if box_model is None:
            try:
                box_model = await self.box_model
            except ElementNotVisible:
                return False
        visible, _ = await self.p_visible(box_model=box_model)
        return visible > minimum_p

    @property
    async def location_once_scrolled_into_view(self) -> dict:
        """
        scrolls to the element and returns the coordinates of it
        """
        await self.scroll_to()
        result = await self.rect
        return {"x": round(result["x"]), "y": round(result["y"])}

    async def scroll_to(self, rect: dict = None):
        """
        scroll to the element

        .. note::
            this isn't properly implemented yet and might be detectable
        """
        args = self._args_builder
        if rect:
            args["rect"] = rect
        try:
            await self.__target__.execute_cdp_cmd("DOM.scrollIntoViewIfNeeded", args)
            return True
        except CDPError as e:
            if e.code == -32000 and 'Node is detached from document' in e.message:
                return False

    @property
    async def size(self) -> dict:
        """**async** The size of the element."""
        box_model = await self.box_model
        return {"height": box_model["height"], "width": box_model["width"]}

    async def value_of_css_property(self, property_name) -> str:
        """
        .. warning::
            NotImplemented

        """
        raise NotImplementedError("you might use javascript instead")

    @property
    async def location(self) -> dict:
        """The location of the element in the renderable canvas."""
        result = await self.rect
        return {"x": round(result["x"]), "y": round(result["y"])}

    @property
    async def rect(self) -> dict:
        """A dictionary with the size and location of the element."""
        # todo: calculate form DOM.getBoxModel
        result = await self.execute_script("return obj.getClientRects()[0].toJSON()", serialization="json",
                                           unique_context=True)
        return result

    @property
    async def css_metrics(self) -> typing.List[dict, float]:
        script = """
            function getRotationAngle(target) 
                {
                  const _obj = window.getComputedStyle(target, null);
                  const matrix = _obj.getPropertyValue('transform');
                  let angle = 0; 
                  if (matrix !== 'none') 
                  {
                    const values = matrix.split('(')[1].split(')')[0].split(',');
                    const a = values[0];
                    const b = values[1];
                    angle = Math.round(Math.atan2(b, a) * (180/Math.PI));
                  } 
                
                  return (angle < 0) ? angle +=360 : angle;
                }
            var _rects = obj.getClientRects()
            var rects = []
            for(let i = 0; i < _rects.length; i++){
                rects.push(_rects[i].toJSON())
            }
            var rotation = getRotationAngle(obj)
            return [rects, rotation]
        """
        return await self.execute_script(script, max_depth=4)

    @property
    async def box_model(self) -> dict:
        """**async** returns the box model of the element. see `DOM.BoxModel <https://vanilla.aslushnikov.com/?DOM.BoxModel>`_
        """
        args = self._args_builder
        try:
            res = await self.__target__.execute_cdp_cmd("DOM.getBoxModel", args)
        except CDPError as e:
            message = 'Could not compute box model.'
            if e.code == -32000 and e.message == 'Cannot find context with specified id':
                raise StaleElementReferenceException(self)
            elif e.code == -32000 and message in e.message:
                raise ElementNotVisible(message)
            else:
                raise e

        model = res['model']
        keys = ['content', 'padding', 'border', 'margin']
        for key in keys:
            quad = model[key]
            model[key] = np.array([[quad[0], quad[1]], [quad[2], quad[3]], [quad[4], quad[5]], [quad[6], quad[7]]])
        return model

    @property
    async def aria_role(self) -> str:
        """**async** Returns the ARIA role of the current web element."""
        # todo: move to CDP
        return await self.get_property("ariaRoleDescription")

    @property
    async def accessible_name(self) -> str:
        """**async** Returns the ARIA Level of the current webelement."""
        # todo: move to CDP
        return await self.get_property("ariaLevel")

    @property
    async def screenshot_as_base64(self) -> str:
        """**async** gets a screenshot as Base64 from the element
        """
        element_data = await self.box_model

        x = element_data["content"][0][0]
        y = element_data["content"][0][1]
        width = element_data["width"]
        height = element_data["height"]

        get_image_bas64 = await self.__target__.execute_cdp_cmd("Page.captureScreenshot", {
            "clip": {
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height),
                "scale": 1
            }
        })
        return get_image_bas64["data"]

    @property
    async def screenshot_as_png(self) -> bytes:
        """**async** Gets the screenshot of the current element as a binary data.
        (PNG format)
        """
        res = await self.screenshot_as_base64
        return b64decode(res.encode("ascii"))

    async def screenshot(self, filename) -> bool:
        """Saves a screenshot of the current element to a PNG image file.

        :param filename: path to save the png to
        """
        if not filename.lower().endswith(".png"):
            warnings.warn(
                "name used for saved screenshot does not match file " "type. It should end with a `.png` extension",
                UserWarning,
            )
        png = await self.screenshot_as_png
        try:
            async with aiofiles.open(filename, "wb") as f:
                await f.write(png)
        except OSError:
            return False
        finally:
            del png
        return True

    @property
    async def parent(self) -> WebElement:
        """**async** The parent element this element"""
        args = {}
        if self._node_id:
            args["nodeId"] = self._node_id
        else:
            args["objectId"] = await self.obj_id
        node: dict = await self._describe()
        node_id = node.get("parentId")
        if node_id:
            if self._loop:
                # noinspection PyUnresolvedReferences
                return await SyncWebElement(node_id=node_id, target=self.__target__, context_id=self.__context_id__,
                                            isolated_exec_id=self.___isolated_exec_id__,
                                            frame_id=await self.__frame_id__)
            else:
                # noinspection PyUnresolvedReferences
                return await WebElement(node_id=node_id, target=self.__target__, context_id=self.__context_id__,
                                        isolated_exec_id=self.___isolated_exec_id__, frame_id=await self.__frame_id__)

    @property
    def children(self):
        return self.find_elements(By.CSS_SELECTOR, "*")

    async def execute_raw_script(self, script: str, *args, await_res: bool = False, serialization: str = None,
                                 max_depth: int = 2, timeout: float = 2, execution_context_id: str = None,
                                 unique_context: bool = True):
        return await self.__exec_raw__(script, *args, await_res=await_res, serialization=serialization,
                                       max_depth=max_depth, timeout=timeout,
                                       execution_context_id=execution_context_id,
                                       unique_context=unique_context)

    async def execute_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                             timeout: float = 2, execution_context_id: str = None, unique_context: bool = True):
        """executes JavaScript synchronously

        .. code-block:: js

            return document

        ``this`` and ``obj`` refers to the element here

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        return await self.__exec__(script, *args, max_depth=max_depth, serialization=serialization,
                                   timeout=timeout, unique_context=unique_context,
                                   execution_context_id=execution_context_id)

    async def execute_async_script(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                                   timeout: float = 2, execution_context_id: str = None, unique_context: bool = True):
        """executes JavaScript asynchronously

        .. warning::
            using execute_async_script is not recommended as it doesn't handle exceptions correctly.
            Use :func:`Chrome.eval_async <selenium_driverless.webdriver.Chrome.eval_async>`

        .. code-block:: js

            resolve = arguments[arguments.length-1]

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        return await self.__exec_async__(script, *args, max_depth=max_depth, serialization=serialization,
                                         timeout=timeout, unique_context=unique_context,
                                         execution_context_id=execution_context_id)

    async def eval_async(self, script: str, *args, max_depth: int = 2, serialization: str = None,
                         timeout: float = 2, execution_context_id: str = None,
                         unique_context: bool = True):
        """executes JavaScript asynchronously

        .. code-block:: js

            res = await fetch("https://httpbin.org/get");
            // mind CORS!
            json = await res.json()
            return json

        ``this`` refers to the element

        see :func:`Target.execute_raw_script <selenium_driverless.types.target.Target.execute_raw_script>` for argument descriptions
        """
        return await self.__eval_async__(script, *args, max_depth=max_depth, serialization=serialization,
                                         timeout=timeout, unique_context=unique_context,
                                         execution_context_id=execution_context_id)

    def __repr__(self):
        return (f'{self.__class__.__name__}("{self.class_name}", '
                f'obj_id={self.__obj_id__}, node_id="{self._node_id}", backend_node_id={self._backend_node_id}, '
                f'context_id={self.__context_id__})')

    def __eq__(self, other):
        if isinstance(other, WebElement):
            if other.__target__ == self.__target__:
                if other.__obj_id__ and self.__obj_id__:
                    return other.__obj_id__.split(".")[0] == self.__obj_id__.split(".")[0]
                elif other._backend_node_id == self._backend_node_id:
                    return True
                elif other._node_id == self._node_id:
                    return True
        return False

    def __ne__(self, other):
        return not self.__eq__(other)
