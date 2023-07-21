from urllib.parse import quote
import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(__file__, '../..'))
sys.path.insert(0, PROJECT_ROOT)

from chromewhip import setup_app
from chromewhip.views import BS
from aiohttp.test_utils import TestClient as tc
HTTPBIN_HOST = 'http://httpbin.org'

RESPONSES_DIR = os.path.join(os.path.dirname(__file__), 'resources/responses')

# TODO: start chrome process in here
# https://docs.pytest.org/en/3.1.3/xunit_setup.html#module-level-setup-teardown

@pytest.mark.asyncio
async def xtest_render_html_basic(event_loop):
    expected = BS(open(os.path.join(RESPONSES_DIR, 'httpbin.org.html.txt')).read()).prettify()
    client = tc(setup_app(loop=event_loop), loop=event_loop)
    await client.start_server()
    resp = await client.get('/render.html?url={}'.format(quote('{}/html'.format(HTTPBIN_HOST))))
    assert resp.status == 200
    text = await resp.text()
    assert expected == text

@pytest.mark.asyncio
async def xtest_render_html_with_js_profile(event_loop):
    expected = BS(open(os.path.join(RESPONSES_DIR, 'httpbin.org.html.after_profile.txt')).read()).prettify()
    profile_name = 'httpbin-org-html'
    profile_path = os.path.join(PROJECT_ROOT, 'tests/resources/js/profiles/{}'.format(profile_name))
    client = tc(setup_app(loop=event_loop, js_profiles_path=profile_path), loop=event_loop)
    await client.start_server()
    resp = await client.get('/render.html?url={}&js={}'.format(
        quote('{}/html'.format(HTTPBIN_HOST)),
        profile_name))
    assert resp.status == 200
    text = await resp.text()
    assert expected == text
