import json
import pytest
import uuid
from urllib import parse


@pytest.mark.asyncio
async def test_fetch(h_driver, subtests, test_server):
    url = test_server.url + "/echo"
    target = h_driver.current_target
    await target.get(url)
    for body in [uuid.uuid4().hex, uuid.uuid4().bytes, {uuid.uuid4().hex: uuid.uuid4().hex}]:
        if isinstance(body, str):
            body_sent = body.encode("utf-8")
        elif isinstance(body, dict):
            body_sent = json.dumps(body).encode("utf-8")
        else:
            body_sent = body

        headers = {uuid.uuid4().hex: uuid.uuid4().hex}
        with subtests.test(body=body):
            res = await target.fetch(url, method="POST", referrer=url, headers=headers, body=body)
            assert res["status_code"] == 200
            for key, value in headers.items():
                assert res["headers"][key] == value
            assert res["body"] == body_sent

    headers = {uuid.uuid4().hex: uuid.uuid4().hex}
    with subtests.test(body=body):
        res = await target.fetch(url, method="GET", referrer=url, headers=headers)
        assert res["status_code"] == 200
        for key, value in headers.items():
            assert res["headers"][key] == value


@pytest.mark.asyncio
async def test_xhr(h_driver, subtests, test_server):
    url = test_server.url + "/echo"
    target = h_driver.current_target
    await target.get(url)
    for body in [uuid.uuid4().hex, uuid.uuid4().hex.encode("utf-8"), {uuid.uuid4().hex: uuid.uuid4().hex}]:
        if isinstance(body, bytes):
            body_sent = body.decode("utf-8")
        elif isinstance(body, dict):
            body_sent = json.dumps(body)
        else:
            body_sent = body

        headers = {uuid.uuid4().hex: uuid.uuid4().hex}
        with subtests.test(body=body):
            res = await target.xhr(url, method="POST", extra_headers=headers, body=body)
            assert res["status"] == 200
            for key, value in headers.items():
                assert res["responseHeaders"][key] == value
            assert res["responseText"] == body_sent

    headers = {uuid.uuid4().hex: uuid.uuid4().hex}
    with subtests.test(body=body):
        res = await target.xhr(url, method="GET", extra_headers=headers)
        assert res["status"] == 200
        for key, value in headers.items():
            assert res["responseHeaders"][key] == value

    with subtests.test(body=body):
        user = uuid.uuid4().hex
        _pass = uuid.uuid4().hex
        resp = uuid.uuid4().hex
        url = test_server.url + "/auth_challenge?" + parse.urlencode(
            {"user": user, "pass": _pass, "resp": resp})

        res = await target.xhr(url, method="GET", user=user, password=_pass)
        assert res["status"] == 200
        assert res["responseText"] == resp
