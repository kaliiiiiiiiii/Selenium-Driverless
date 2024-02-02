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

# edited by github/kaliiiiiiiiii

"""The By implementation."""

from typing import Literal


# noinspection PyPep8Naming
class By:
    """Set of supported locator strategies."""

    @property
    def ID(self) -> Literal["id"]:
        """by element ID"""
        return "id"

    @property
    def XPATH(self) -> Literal["xpath"]:
        """by XPATH to the element"""
        return "xpath"

    @property
    def NAME(self) -> Literal["name"]:
        """by the name of the element"""
        return "name"

    @property
    def TAG_NAME(self) -> Literal["tag name"]:
        """by the tag name of the element"""
        return "tag name"

    @property
    def CLASS_NAME(self) -> Literal["class name"]:
        """by the class name of the element"""
        return "class name"

    @property
    def CSS_SELECTOR(self) -> Literal["css selector"]:
        """by the CSS selector of the element"""
        return "css selector"

    @property
    def CSS(self) -> Literal["css selector"]:
        """by the CSS selector of the element

        alias to :func:`By.CSS_SELECTOR <selenium_driverless.types.by.By.CSS_SELECTOR>`
        """
        return self.CSS_SELECTOR
