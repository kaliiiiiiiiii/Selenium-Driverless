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
# edited by kaliiiiiiiiiii

import warnings
from base64 import b64decode

from selenium.webdriver.common.by import By

from selenium_driverless.types import JSEvalException, RemoteObject
from selenium_driverless.input.pointer import Pointer
from selenium_driverless.scripts.geometry import gen_heatmap, gen_rand_point, centroid

from cdp_socket.exceptions import CDPError

import numpy as np


class NoSuchElementException(Exception):
    pass


class StaleElementReferenceException(Exception):
    pass


class ElementNotVisible(Exception):
    pass


class ElementNotInteractable(Exception):
    def __init__(self, x: float, y: float):
        super().__init__(f"element not interactable at x:{x}, y:{y}, it might be hidden under another one")


# noinspection PyProtectedMember
class WebElement(RemoteObject):
    """Represents a DOM element.

    Generally, all interesting operations that interact with a document will be
    performed through this interface.

    All method calls will do a freshness check to ensure that the element
    reference is still valid.  This essentially determines whether the
    element is still attached to the DOM.  If this test fails, then an
    ``StaleElementReferenceException`` is thrown, and all future calls to this
    instance will fail.
    """

    def __init__(self, driver, js: str = None, obj_id=None, node_id=None, check_existence=True, loop=None) -> None:
        self._loop = loop
        if not (obj_id or node_id or js):
            raise ValueError("either js, obj_id or node_id need to be specified")
        self._node_id = node_id
        super().__init__(driver=driver, js=js, obj_id=obj_id, check_existence=check_existence)

    def __await__(self):
        return super().__await__()

    async def __aenter__(self):
        if self._check_exist:
            await self.obj_id

        # noinspection PyUnusedLocal
        async def clear_node_id(data):
            if not self._obj_id:
                await self.obj_id
            self._node_id = None

        await self._driver.add_cdp_listener("Page.loadEventFired", clear_node_id)

        return self

    @property
    async def obj_id(self):
        if not self._obj_id:
            if self._js:
                res = await self._driver.execute_cdp_cmd("Runtime.evaluate",
                                                         {"expression": self._js,
                                                          "serializationOptions": {
                                                              "serialization": "idOnly"}})
                if "exceptionDetails" in res.keys():
                    raise JSEvalException(res["exceptionDetails"])
                res = res["result"]
                self._obj_id = res['objectId']
                if res["subtype"] != "node":
                    raise ValueError("object isn't a node")
            else:
                res = await self._driver.execute_cdp_cmd("DOM.resolveNode", {"nodeId": self._node_id})
                self._obj_id = res["object"]["objectId"]
        return self._obj_id

    @property
    async def node_id(self):
        if not self._node_id:
            node = await self._driver.execute_cdp_cmd("DOM.requestNode", {"objectId": await self.obj_id})
            self._node_id = node["nodeId"]
        return self._node_id

    async def find_element(self, by: str, value: str, idx: int = 0):
        """Find an element given a By strategy and locator.

        :Usage:
            ::

                element = element.find_element(By.ID, 'foo')

        :rtype: WebElement
        """
        elems = await self.find_elements(by=by, value=value)
        if not elems:
            raise NoSuchElementException()
        return elems[idx]

    async def find_elements(self, by: str = By.ID, value: str or None = None, warn: bool = True):
        """Find elements given a By strategy and locator.

        :Usage:
            ::

                element = element.find_elements(By.CLASS_NAME, 'foo')

        :rtype: list of WebElement
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
            if warn:
                warnings.warn(
                    f'By.TAG_NAME might be detectable, you might use driver.search_elements("{value}") or By.CSS_SELECTOR instead')
            return await self.execute_script("return this.getElementsByTagName(arguments[0])",
                                             value, serialization="deep")
        elif by == By.CSS_SELECTOR:
            elems = []
            res = await self._driver.execute_cdp_cmd("DOM.querySelectorAll", {"nodeId": await self.node_id,
                                                                              "selector": value})
            node_ids = res["nodeIds"]
            for node_id in node_ids:
                if self._loop:
                    from selenium_driverless.sync.webelement import WebElement as SyncWebElement
                    elem = SyncWebElement(node_id=node_id, driver=self._driver, check_existence=False, loop=self._loop)
                else:
                    elem = await WebElement(node_id=node_id, driver=self._driver, check_existence=False)
                elems.append(elem)
            return elems
        elif by == By.XPATH:
            scipt = """return document.evaluate(
                          arguments[0],
                          this,
                          null,
                          XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
                          null,
                        );"""
            if warn:
                warnings.warn(
                    f'By.XPATH might be detectable, you might use driver.search_elements("{value}") or By.CSS_SELECTOR instead')
            return await self.execute_script(scipt, value, serialization="deep")
        else:
            return ValueError("unexpected by")

    async def _describe(self):
        res = await self._driver.execute_cdp_cmd("DOM.describeNode", {"objectId": await self.obj_id, "pierce": True})
        return res["node"]

    @property
    async def source(self):
        res = await self._driver.execute_cdp_cmd("DOM.getOuterHTML", {"nodeId": await self.node_id})
        return res["outerHTML"]

    async def set_source(self, value: str):
        await self._driver.execute_cdp_cmd("DOM.setOuterHTML", {"nodeId": await self.node_id, "outerHTML": value})

    async def get_property(self, name: str):
        """Gets the given property of the element.

        :Args:
            - name - Name of the property to retrieve.

        :Usage:
            ::

                text_length = target_element.get_property("text_length")
        """
        return await self.execute_script(f"return this[arguments[0]]", name, warn=True)

    @property
    async def tag_name(self) -> str:
        """This element's ``tagName`` property."""
        node = await self._describe()
        return node["localName"]

    @property
    async def text(self) -> str:
        """The text of the element."""
        return await self.get_property("textContent")

    @property
    async def value(self) -> str:
        """The value of the element."""
        return await self.get_property("value")

    async def clear(self) -> None:
        """Clears the text if it's a text entry element."""
        await self.execute_script("this.value = ''", warn=True)

    async def remove(self):
        await self._driver.execute_cdp_cmd("DOM.removeNode", {"nodeId": await self.node_id})

    async def highlight(self, highlight=True):
        if highlight:
            await self._driver.execute_cdp_cmd("Overlay.enable")
            await self._driver.execute_cdp_cmd("Overlay.highlightNode", {"nodeId": await self.node_id,
                                                                         "highlightConfig": {
                                                                             "showInfo": True,
                                                                             "borderColor": {
                                                                                 "r": 76, "g": 175, "b": 80, "a": 1
                                                                             },
                                                                             "contentColor": {
                                                                                 "r": 76, "g": 175, "b": 80, "a": 0.24
                                                                             },
                                                                             "shapeColor": {
                                                                                 "r": 76, "g": 175, "b": 80, "a": 0.24
                                                                             }
                                                                         }})
        else:
            await self._driver.execute_cdp_cmd("Overlay.disable")

    async def focus(self):
        return await self._driver.execute_cdp_cmd("DOM.focus", {"objectId": await self.obj_id})

    async def click(self, timeout: float = 0.25, bias: float = 5, resolution: int = 50, debug: bool = False, scroll_to=True) -> None:
        """Clicks the element."""
        if scroll_to:
            await self.scroll_to()

        while True:
            try:
                x, y = await self.mid_location(bias=bias, resolution=resolution, debug=debug)

                res = await self._driver.execute_cdp_cmd("DOM.getNodeForLocation", {"x": x, "y": y,
                                                                                    "includeUserAgentShadowDOM": True,
                                                                                    "ignorePointerEventsNone": False})
                node_id_at = res["nodeId"]
                res = await self._driver.execute_cdp_cmd("DOM.resolveNode", {"nodeId": node_id_at})
                obj_id_at = res["object"]["objectId"]
                this_obj_id = await self.obj_id

                if obj_id_at.split(".")[0] != this_obj_id.split(".")[0]:
                    raise ElementNotInteractable(x, y)
                p = Pointer(driver=self._driver)
                await p.click(x=x, y=y, timeout=timeout)
                break
            except CDPError as e:
                # element partially within viewport, point outside viewport
                # todo: make sure point is within viewport at def mid_location
                if not (e.code == -32000 and e.message == 'No node found at given location'):
                    raise e

    async def write(self, text: str):
        await self.focus()
        await self._driver.execute_cdp_cmd("Input.insertText", {"text": text})

    async def send_keys(self, value: str) -> None:
        # noinspection GrazieInspection
        """Simulates typing into the element.

                :Args:
                    - value - A string for typing, or setting form fields.  For setting
                      file inputs, this could be a local file path.

                Use this to send simple key events or to fill out form fields::

                    form_textfield = driver.find_element(By.NAME, 'username')
                    form_textfield.send_keys("admin")

                This can also be used to set file inputs.

                ::

                    file_input = driver.find_element(By.NAME, 'profilePic')
                    file_input.send_keys("path/to/profilepic.gif")
                    # Generally it's better to wrap the file path in one of the methods
                    # in os.path to return the actual path to support cross OS testing.
                    # file_input.send_keys(os.path.abspath("path/to/profilepic.gif"))
                """
        # transfer file to another machine only if remote driver is used
        # the same behaviour as for java binding
        raise NotImplementedError("you might use elem.write() for inputs instead")

    async def mid_location(self, bias: float = 5, resolution: int = 50, debug: bool = False):
        """
        returns random location in element with probability close to the middle
        """

        box = await self.box_model
        vertices = box["content"]
        if bias and resolution:
            heatmap = gen_heatmap(vertices, num_points=resolution)
            point = gen_rand_point(vertices, heatmap, bias_value=bias)
            if debug:
                from selenium_driverless.scripts.geometry import visualize
                visualize(np.array([point]), heatmap, vertices)
        else:
            point = centroid(vertices)

        return [int(point[0]), int(point[1])]

    async def submit(self):
        """Submits a form."""
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
        return await self.execute_script(script, warn=True)

    async def get_dom_attribute(self, name: str) -> str:
        """Gets the given attribute of the element. Unlike
        :func:`~selenium.webdriver.remote.BaseWebElement.get_attribute`, this
        method only returns attributes declared in the element's HTML markup.

        :Args:
            - name - Name of the attribute to retrieve.

        :Usage:
            ::

                text_length = target_element.get_dom_attribute("class")
        """
        attr_str: list = await self._driver.execute_cdp_cmd("DOM.getAttributes", {"nodeId": await self.node_id})
        for attr in attr_str:
            key, value = attr.split("=")
            if key == name:
                return value[1:-1]

    async def set_dom_attribute(self, name: str, value: str):
        self._driver.execute_cdp_cmd("DOM.setAttributeValue", {"nodeId": await self.node_id,
                                                               "name": name, "value": value})

    async def get_attribute(self, name):
        """Gets the given attribute or property of the element.

        This method will first try to return the value of a property with the
        given name. If a property with that name doesn't exist, it returns the
        value of the attribute with the same name. If there's no attribute with
        that name, ``None`` is returned.

        Values which are considered truthy, that is equals "true" or "false",
        are returned as booleans.  All other non-``None`` values are returned
        as strings.  For attributes or properties which do not exist, ``None``
        is returned.

        To obtain the exact value of the attribute or property,
        use :func:`~selenium.webdriver.remote.BaseWebElement.get_dom_attribute` or
        :func:`~selenium.webdriver.remote.BaseWebElement.get_property` methods respectively.

        :Args:
            - name - Name of the attribute/property to retrieve.

        Example::

            # Check if the "active" CSS class is applied to an element.
            is_active = "active" in target_element.get_attribute("class")
        """
        return await self.get_property(name)

    async def is_selected(self) -> bool:
        """Returns whether the element is selected.

        Can be used to check if a checkbox or radio button is selected.
        """
        result = await self.get_attribute("checked")
        if result:
            return True
        else:
            return False

    async def is_enabled(self) -> bool:
        """Returns whether the element is enabled."""
        return not await self.get_property("disabled")

    @property
    async def shadow_root(self):
        """Returns a shadow root of the element if there is one or an error.
        Only works from Chromium 96, Firefox 96, and Safari 16.4 onwards.

        :Returns:
          - ShadowRoot object or
          - NoSuchShadowRoot - if no shadow root was attached to element
        """
        # todo: move to CDP
        return await self.get_property("ShadowRoot")

    # RenderedWebElement Items
    async def is_displayed(self) -> bool:
        """Whether the element is visible to a user."""
        # Only go into this conditional for browsers that don't use the atom themselves
        size = await self.size
        return not (size["height"] == 0 or size["width"] == 0)

    @property
    async def location_once_scrolled_into_view(self) -> dict:
        """THIS PROPERTY MAY CHANGE WITHOUT WARNING. Use this to discover where
        on the screen an element is so that we can click it. This method should
        cause the element to be scrolled into view.

        Returns the top lefthand corner location on the screen, or zero
        coordinates if the element is not visible.
        """
        await self.scroll_to()
        result = await self.rect
        return {"x": round(result["x"]), "y": round(result["y"])}

    async def scroll_to(self, rect: dict = None):
        args = {"objectId": await self.obj_id}
        if rect:
            args["rect"] = rect
        await self._driver.execute_cdp_cmd("DOM.scrollIntoViewIfNeeded", args)

    @property
    async def size(self) -> dict:
        """The size of the element."""
        size = await self.rect
        return {"height": size["height"], "width": size["width"]}

    async def value_of_css_property(self, property_name) -> str:
        """The value of a CSS property."""
        raise NotImplementedError("you might use get_attribute instead")

    @property
    async def location(self) -> dict:
        """The location of the element in the renderable canvas."""
        result = await self.rect
        return {"x": round(result["x"]), "y": round(result["y"])}

    @property
    async def rect(self) -> dict:
        """A dictionary with the size and location of the element."""
        # todo: calculate form DOM.getBoxModel
        result = await self.execute_script("return this.getBoundingClientRect().toJSON()", serialization="json")
        return result

    @property
    async def box_model(self):
        node_id = await self.node_id
        res = await self._driver.execute_cdp_cmd("DOM.getBoxModel", {"nodeId": node_id})
        model = res['model']
        keys = ['content', 'padding', 'border', 'margin']
        for key in keys:
            quad = model[key]
            model[key] = np.array([[quad[0], quad[1]], [quad[2], quad[3]], [quad[4], quad[5]], [quad[6], quad[7]]])
        return model

    @property
    async def aria_role(self) -> str:
        """Returns the ARIA role of the current web element."""
        # todo: move to CDP
        return await self.get_property("ariaRoleDescription")

    @property
    async def accessible_name(self) -> str:
        """Returns the ARIA Level of the current webelement."""
        # todo: move to CDP
        return await self.get_property("ariaLevel")

    @property
    async def screenshot_as_base64(self) -> str:
        """Gets the screenshot of the current element as a base64 encoded
        string.

        :Usage:
            ::

                img_b64 = element.screenshot_as_base64
        """
        raise NotImplementedError()

    @property
    async def screenshot_as_png(self) -> bytes:
        """Gets the screenshot of the current element as a binary data.

        :Usage:
            ::

                element_png = element.screenshot_as_png
        """
        res = await self.screenshot_as_base64
        return b64decode(res.encode("ascii"))

    async def screenshot(self, filename) -> bool:
        """Saves a screenshot of the current element to a PNG image file.
        Returns False if there is any IOError, else returns True. Use full
        paths in your filename.

        :Args:
         - filename: The full path you wish to save your screenshot to. This
           should end with a `.png` extension.

        :Usage:
            ::

                element.screenshot('/Screenshots/foo.png')
        """
        if not filename.lower().endswith(".png"):
            warnings.warn(
                "name used for saved screenshot does not match file " "type. It should end with a `.png` extension",
                UserWarning,
            )
        png = await self.screenshot_as_png
        try:
            with open(filename, "wb") as f:
                f.write(png)
        except OSError:
            return False
        finally:
            del png
        return True

    @property
    async def parent(self):
        """The parent of this element"""
        args = {}
        if self._node_id:
            args["nodeId"] = self._node_id
        else:
            args["objectId"] = await self.obj_id
        node: dict = await self._describe()
        node_id = node.get("parentId", None)
        if node_id:
            return WebElement(node_id=node_id, check_existence=False, driver=self._driver)

    @property
    def children(self):
        return self.find_elements(By.CSS_SELECTOR, "*")
