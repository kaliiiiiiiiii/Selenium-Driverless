import pytest
import uuid
from urllib import parse
from selenium_driverless.scripts.network_interceptor import NetworkInterceptor, InterceptedAuth


async def on_auth(request: InterceptedAuth, user, _pass):
    await request.continue_auth(response="ProvideCredentials", username=user, password=_pass)


def gen_url(test_server):
    user = uuid.uuid4().hex
    _pass = uuid.uuid4().hex
    resp = uuid.uuid4().hex
    url = test_server.url + "/auth_challenge?" + parse.urlencode(
        {"user": user, "pass": _pass, "resp": resp})
    return user, _pass, resp, url


@pytest.mark.asyncio
async def test_auth_extension(h_driver, subtests, test_server):
    user, _pass, resp, url = gen_url(test_server)

    with subtests.test():
        await h_driver.get(url, timeout=1)
        response = await h_driver.execute_script("return document.body.textContent")
        assert response != resp

    with subtests.test():
        await h_driver.set_auth(user, _pass, f"{test_server.host}:{test_server.port}")
        await h_driver.get(url, timeout=1)
        response = await h_driver.execute_script("return document.body.textContent")
        assert response == resp


@pytest.mark.asyncio
async def test_auth_interceptor(h_driver, subtests, test_server):
    user, _pass, resp, url = gen_url(test_server)

    with subtests.test():
        await h_driver.get(url, timeout=1)
        response = await h_driver.execute_script("return document.body.textContent")
        assert response != resp

    with subtests.test():
        async with NetworkInterceptor(h_driver, on_auth=lambda r: on_auth(r, user, _pass), intercept_auth=True):
            await h_driver.get(url, timeout=1)
        response = await h_driver.execute_script("return document.body.textContent")
        assert response == resp

    with subtests.test():
        # todo: fixme
        await h_driver.get(url, timeout=10)
        response = await h_driver.execute_script("return document.body.textContent")
        assert response == resp
