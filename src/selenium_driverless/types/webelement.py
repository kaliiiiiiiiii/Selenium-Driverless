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
from selenium.webdriver.remote.shadowroot import ShadowRoot

from selenium_driverless.types import JSEvalException, RemoteObject


class NoSuchElementException(Exception):
    pass


class StaleElementReferenceException(Exception):
    pass


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

    def __init__(self, driver, js: str = None, obj_id=None, parent=None, check_existence=True) -> None:
        self._loop = None
        if not parent:
            self._parent = WebElement(js="document", driver=driver, parent="undefined", check_existence=False)
        elif parent == "undefined":
            self._parent = None
        super().__init__(driver=driver, js=js, obj_id=obj_id, check_existence=check_existence)

    def __await__(self):
        return super().__await__()

    @property
    async def obj_id(self):
        if not self._obj_id:
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
        return self._obj_id

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

    async def find_elements(self, by=By.ID, value=None, base_element=None):
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
            return await self.execute_script("return this.getElementsByTagName(arguments[0])",
                                             value, serialization="deep")
        elif by == By.CSS_SELECTOR:
            return await self.execute_script("return this.querySelectorAll(arguments[0])",
                                             value, serialization="deep")
        elif by == By.XPATH:
            scipt = """return this.evaluate(
                          arguments[0],
                          this,
                          null,
                          XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
                          null,
                        );"""
            return await self.execute_script(scipt, value, serialization="deep")
        else:
            return ValueError("unexpected by")

    @property
    async def source(self):
        return await self.get_property("outerHTML")

    async def get_property(self, name: str):
        """Gets the given property of the element.

        :Args:
            - name - Name of the property to retrieve.

        :Usage:
            ::

                text_length = target_element.get_property("text_length")
        """
        return await self.execute_script(f"return this[arguments[0]]", name)

    @property
    async def tag_name(self) -> str:
        """This element's ``tagName`` property."""
        return await self.get_property("tagName")

    @property
    async def text(self) -> str:
        """The text of the element."""
        return await self.get_property("textContent")

    async def click(self) -> None:
        """Clicks the element."""
        await self.execute_script("this.click()")

    async def submit(self):
        """Submits a form."""
        script = (
            "/* submitForm */var form = self;\n"
            'while (form.nodeName != "FORM" && form.parentNode) {\n'
            "  form = form.parentNode;\n"
            "}\n"
            "if (!form) { throw Error('Unable to find containing form element'); }\n"
            "if (!form.ownerDocument) { throw Error('Unable to find owning document'); }\n"
            "var e = form.ownerDocument.createEvent('Event');\n"
            "e.initEvent('submit', true, true);\n"
            "if (form.dispatchEvent(e)) { HTMLFormElement.prototype.submit.call(form) }\n"
        )
        return await self.execute_script(script)

    async def clear(self) -> None:
        """Clears the text if it's a text entry element."""
        await self.execute_script("this.reset()")

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
        raise NotImplementedError("you might use get_attribute instead")

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
        return await self.get_property(name=name)

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

    async def send_keys(self, value: str) -> None:
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
        await self.execute_script("this.value = this.value+arguments[0]", value)

    @property
    async def shadow_root(self) -> ShadowRoot:
        """Returns a shadow root of the element if there is one or an error.
        Only works from Chromium 96, Firefox 96, and Safari 16.4 onwards.

        :Returns:
          - ShadowRoot object or
          - NoSuchShadowRoot - if no shadow root was attached to element
        """
        raise NotImplementedError()

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
        "arguments[0].scrollIntoView(true); return arguments[0].getBoundingClientRect()"
        self.t.exec(self.t.path("scrollIntoView", obj=self._raw), args=[True])
        result = self.rect
        return {"x": round(result["x"]), "y": round(result["y"])}

    @property
    async def size(self) -> dict:
        """The size of the element."""
        size = await self.rect
        return {"height": size["height"], "width": size["width"]}

    def value_of_css_property(self, property_name) -> str:
        """The value of a CSS property."""
        raise NotImplementedError("you might use get_attribute instead")

    @property
    def location(self) -> dict:
        """The location of the element in the renderable canvas."""
        result = self.rect
        return {"x": round(result["x"]), "y": round(result["y"])}

    @property
    async def rect(self) -> dict:
        """A dictionary with the size and location of the element."""
        result = await self.execute_script("this.getBoundingClientRect()", only_value=False, serialization="deep")
        return result

    @property
    def _rect(self):
        return self.t.exec(self.t.path("", obj=self._raw))

    @property
    def aria_role(self) -> str:
        """Returns the ARIA role of the current web element."""
        return self.get_property("ariaRoleDescription")

    @property
    def accessible_name(self) -> str:
        """Returns the ARIA Level of the current webelement."""
        return self.get_property("ariaLevel")

    @property
    def screenshot_as_base64(self) -> str:
        """Gets the screenshot of the current element as a base64 encoded
        string.

        :Usage:
            ::

                img_b64 = element.screenshot_as_base64
        """
        raise NotImplementedError()

    @property
    def screenshot_as_png(self) -> bytes:
        """Gets the screenshot of the current element as a binary data.

        :Usage:
            ::

                element_png = element.screenshot_as_png
        """
        return b64decode(self.screenshot_as_base64.encode("ascii"))

    def screenshot(self, filename) -> bool:
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
        png = self.screenshot_as_png
        try:
            with open(filename, "wb") as f:
                f.write(png)
        except OSError:
            return False
        finally:
            del png
        return True

    @property
    def parent(self):
        """Internal reference to the WebDriver instance this element was found
        from."""
        return self._parent

    @property
    def children(self):
        return self.find_elements(By.CSS_SELECTOR, "*")

    def _css_selector(self, current=False):
        def getter():
            from selenium_driverless.types import JSEvalException
            script = self.t.exec(self.t.path("CSSSelector", obj=self.t.this()), args=[self._raw])
            try:
                return self._injector.tabs.exec(type_dict=script, tab_id=self._tab_id)["result"][0]
            except JSEvalException as e:
                if e.message[:25] == "Cannot read properties of":
                    # is window.document
                    return ""
                else:
                    raise e

        if not self._persistent_css_selector:
            self._persistent_css_selector = getter()
        if current:
            return getter()
        return self._persistent_css_selector

    # noinspection PyStatementEffect
