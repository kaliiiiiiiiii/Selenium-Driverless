import json

import pytest

from chromewhip import helpers
from chromewhip.protocol import page


def test_valid_json_to_event():
    valid_payload = {"method": "Page.frameNavigated", "params": {
        "frame": {"id": "3635.1", "loaderId": "3635.1", "url": "http://httpbin.org/html",
                  "securityOrigin": "http://httpbin.org", "mimeType": "text/html"}}}

    event = helpers.json_to_event(valid_payload)
    assert event.__class__ == page.FrameNavigatedEvent
    assert event.frame.loaderId == "3635.1"


def test_invalid_method_json_to_event():
    valid_payload = {"method": "Page.invalidEvent", "params": {
        "frame": {"id": "3635.1", "loaderId": "3635.1", "url": "http://httpbin.org/html",
                  "securityOrigin": "http://httpbin.org", "mimeType": "text/html"}}}
    with pytest.raises(AttributeError) as exc_info:
        helpers.json_to_event(valid_payload)


def test_json_encoder_event():
    f = page.Frame(1, 'test', 'http://example.com', 'test', 'text/html')
    fe = page.FrameNavigatedEvent(f)
    payload = json.dumps(fe, cls=helpers.ChromewhipJSONEncoder)
    assert payload.count('"method":') == 1
    assert payload.count('"params":') == 1


def test_json_encoder_type():
    f = page.Frame(1, 'test', 'http://example.com', 'test', 'text/html')
    payload = json.dumps(f, cls=helpers.ChromewhipJSONEncoder)
    assert payload.count('"id": 1') == 1
    assert payload.count('"url": "http://example.com"') == 1


def test_hash_from_concrete_event():
    f = page.Frame(3, 'test', 'http://example.com', 'test', 'text/html')
    fe = page.FrameNavigatedEvent(f)
    assert fe.hash_() == "Page.frameNavigated:frameId=3"


def test_build_hash_from_event_cls():
    hash = page.FrameNavigatedEvent.build_hash(frameId=3)
    assert hash == "Page.frameNavigated:frameId=3"


