# https://github.com/pytest-dev/pytest-asyncio/issues/52
# pytest_plugins = 'aiohttp.pytest_plugin'

import pytest
import os
import sys

PACKAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

sys.path.append(PACKAGE_DIR)

