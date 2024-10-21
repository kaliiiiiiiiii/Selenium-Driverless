import asyncio
import typing
import uuid
from enum import Enum

import aiohttp
from selenium_driverless.webdriver import Chrome
from selenium_driverless.types.target import Target
from selenium_driverless.types.base_target import BaseTarget
import websockets

from cdp_socket.exceptions import CDPError

import base64

PatternsType = typing.List[typing.Dict[str, str]]


# TODO: support OrderedDict instead of List[Fetch.HeaderEntry]


class RequestDoneException(Exception):
    """raised when the request or auth challenge has already been resumed"""
    def __init__(self, data: typing.Union["InterceptedRequest", "InterceptedAuth"]):
        data._done = True
        super().__init__(f'request or auth challenge with url:"{data.request.url}" has already been resumed')
        self._data = data

    @property
    def request(self) -> typing.Union["InterceptedRequest", "InterceptedAuth"]:
        """the corresponding request or auth challenge"""
        return self._data


class AuthAlreadyHandledException(Exception):
    """raised when an auth challenge has already been handled by an external application (for example chrome-extension)"""
    def __init__(self, data: "InterceptedAuth"):
        data._done = True
        super().__init__(
            f'Auth for url"{data.request.url}" has already been handled by an external application (for example chrome-extension)')
        self._data = data

    @property
    def request(self) -> "InterceptedAuth":
        """the corresponding auth challenge"""
        return self._data


class RequestStages:
    Request = 0
    """stage at request"""

    Response = 1
    """stage at response"""


class RequestPattern(Enum):
    AnyRequest = {"urlPattern": "*", "requestStage": "Request"}
    """pattern for any request"""

    AnyResponse = {"urlPattern": "*", "requestStage": "Response"}
    """pattern for any response"""

    @staticmethod
    def new(url_pattern: str = None,
            resource_type: typing.Literal[
                "Document", "Stylesheet", "Image", "Media", "Font", "Script", "TextTrack", "XHR", "Fetch", "Prefetch", "EventSource", "WebSocket", "Manifest", "SignedExchange", "Ping", "CSPViolationReport", "Preflight", "Other"] = None,
            request_stage: typing.Literal["Request", "Response"] = None):
        """
        create a new request pattern
        """
        pattern = {}
        if url_pattern:
            pattern["urlPattern"] = url_pattern
        if resource_type:
            pattern["resourceType"] = resource_type
        if request_stage:
            pattern["requestStage"] = request_stage


class Request:
    def __init__(self, params, target):
        self._params = params
        self._target = target

    @property
    def target(self) -> typing.Union[Target, BaseTarget]:
        """the target"""
        return self._target

    @property
    def params(self) -> dict:
        """the parameters from `Network.Request <https://chromedevtools.github.io/devtools-protocol/tot/Network/#type-Request>`_ as a dict"""
        return self._params

    @property
    def url(self) -> str:
        """Request URL (without fragment)."""
        return self._params["url"]

    @property
    def url_fragment(self) -> typing.Union[str, None]:
        """Fragment of the requested URL starting with hash, if present."""
        return self._params.get("urlFragment")

    @property
    def method(self) -> typing.Union[str, None]:
        """HTTP request method."""
        return self._params.get("method")

    @property
    def headers(self) -> typing.Dict[str, str]:
        """Request / response headers as keys / values of JSON object."""
        return self._params["headers"]

    @property
    def post_data(self) -> typing.Union[str, None]:
        """HTTP POST request data"""
        return self._params.get("postData")

    @property
    def has_post_data(self) -> typing.Union[bool, None]:
        """True when the request has POST data. Note that postData might still be omitted when this flag is true when the data is too long."""
        return self._params.get("hasPostData")

    @property
    def post_data_entries(self) -> typing.Union[typing.List[str], None]:
        """an array of `Network.PostDataEntry <https://chromedevtools.github.io/devtools-protocol/tot/Network/#type-PostDataEntry>`_"""
        return self._params.get("postDataEntries")

    @property
    def mixed_content_type(self) -> typing.Literal["blockable", "optionally-blockable", "none", None]:
        """The mixed content type of the request."""
        return self._params.get("mixedContentType")

    @property
    def initial_priority(self) -> typing.Literal["VeryLow", "Low", "Medium", "High", "VeryHigh", None]:
        """Priority of the resource request at the time request is sent."""
        return self._params["initialPriority"]

    @property
    def referrer_policy(self) -> typing.Literal["unsafe-url", "no-referrer-when-downgrade", "no-referrer", "origin", "origin-when-cross-origin", "same-origin", "strict-origin", "strict-origin-when-cross-origin"]:
        """
        The referrer policy of the request, as defined in `w3.org/TR/referrer-policy <https://www.w3.org/TR/referrer-policy/>`_
        """
        return self._params["referrerPolicy"]

    @property
    def is_link_preload(self) -> typing.Union[bool, None]:
        """Whether is loaded via link preload."""
        return self._params.get("isLinkPreload")

    @property
    def trust_token_params(self) -> typing.Union[dict, None]:
        """see `Network.TrustTokenParams <https://chromedevtools.github.io/devtools-protocol/tot/Network/#type-TrustTokenParams>`_ for reference"""
        return self._params.get("trustTokenParams")

    @property
    def is_same_site(self) -> typing.Union[bool, None]:
        """
        True if this resource request is considered to be the 'same site' as the request corresponding to the main frame.
        """
        return self._params.get("isSameSite")

    def __repr__(self):
        return self.params.__repr__()


class AuthChallenge:
    def __init__(self, params, target):
        self._params = params
        self._target = target

    @property
    def target(self) -> typing.Union[Target, BaseTarget]:
        """the target"""
        return self._target

    @property
    def params(self) -> dict:
        """the parameters from `Fetch.AuthChallenge <https://chromedevtools.github.io/devtools-protocol/tot/Fetch/#type-AuthChallenge>`_ as a dict"""
        return self._params

    @property
    def source(self) -> typing.Literal["Server", "Proxy"]:
        """Source of the authentication challenge"""
        return self.params.get("source")

    @property
    def origin(self) -> str:
        """Origin of the challenger."""
        return self.params["origin"]

    @property
    def scheme(self) -> str:
        """The authentication scheme used, such as basic or digest"""
        return self.params["scheme"]

    @property
    def realm(self) -> str:
        """corresponding value for ``Please enter your username and password for <realm name>:``"""
        return self.params["realm"]

    def __repr__(self):
        return self.params.__repr__()


class InterceptedRequest:
    def __init__(self, params, target):
        self._params = params
        self._target = target
        self._done = False
        self._stage = None
        self._is_redirect = None
        self._body = False
        self._request = None
        self.timeout = 10

    @property
    def target(self) -> typing.Union[Target, BaseTarget]:
        """the target"""
        return self._target

    @property
    def stage(self) -> typing.Literal[0, 1]:
        """
        one of :func:`RequestStages.Request <selenium_driverless.scripts.network_interceptor.RequestStages.Request>`, :func:`RequestStages.Response <selenium_driverless.scripts.network_interceptor.RequestStages.Response>`
        0 => Request
        1 => Response
        """
        if self._stage is None:
            if self.response_status_code or self.response_error_reason:
                self._stage = RequestStages.Response
            else:
                self._stage = RequestStages.Request
        return self._stage

    @property
    def is_redirect(self):
        """
        if the response is a redirect (response_status_code in [301, 302, 303, 307, 308])
        """
        if self._is_redirect is None:
            if self.response_status_code and (self.response_status_code in [301, 302, 303, 307, 308]):
                self._is_redirect = True
            else:
                self._is_redirect = False
        return self._is_redirect

    @property
    def params(self) -> dict:
        """the parameters from `Fetch.requestPaused <https://chromedevtools.github.io/devtools-protocol/tot/Fetch/#event-requestPaused>`_ as a dict"""
        return self._params

    @property
    def frame_id(self) -> str:
        """the ``Page.FrameId`` of the frame that initiated the request"""
        return self._params["frameId"]

    @property
    def request(self) -> Request:
        """the corresponding request"""
        if self._request is None:
            self._request = Request(self._params["request"], self.target)
        return self._request

    @property
    def id(self) -> str:
        """``Fetch.RequestId``"""
        return self._params["requestId"]

    @property
    def resource_type(self) -> str:
        """
        ``Network.resourceType``
        """
        return self._params["resourceType"]

    @property
    def network_id(self) -> typing.Union[str, None]:
        """
        the ``Network.RequestId`` if a corresponding ``Network.requestWillBeSent`` event had been fired
        """
        return self._params.get("networkId")

    @property
    def response_error_reason(self) -> typing.Union[str, None]:
        """
        response error-reason at response stage
        """
        return self._params.get("responseErrorReason")

    @property
    def response_headers(self) -> typing.Union[typing.List[typing.Dict[str, str]], None]:
        """
        the headers at response stage
        """
        return self._params.get("responseHeaders")

    @property
    def response_status_code(self) -> typing.Union[int, None]:
        """
        the status code at response stage
        """
        return self._params.get("responseStatusCode")

    @property
    def response_status_text(self) -> typing.Union[str, None]:
        """
        the status text at response stage
        """
        return self._params.get("responseStatusText")

    @property
    def redirected_id(self) -> typing.Union[str, None]:
        """
        ``Fetch.requestId`` reference id to the request that caused the redirect
        """
        return self._params.get("redirectedRequestId")

    @property
    async def body(self) -> typing.Union[bytes, None]:
        """**async**
        get the response body for a request

        .. note::
            this uses network and might take some time

        """
        if self._body is False:
            body = await self.target.execute_cdp_cmd("Fetch.getResponseBody", {"requestId": self.id},
                                                     timeout=self.timeout)
            body = body.get('body')
            if body:
                self._body = base64.b64decode(body)
            else:
                self._body = None
        return self._body

    async def bypass_browser(self, auth: aiohttp.BasicAuth = None, allow_redirects=True, compress: bool = None,
                             proxy: str = None, proxy_auth: aiohttp.BasicAuth = None, timeout: float = None):
        """
        bypass browser by making the request externally

        .. warning::
            this method does not change the TLS fingerprint accordingly and is technically detectable

        """
        if self._done:
            raise RequestDoneException(self)
        else:
            async with aiohttp.request(method=self.request.method, url=self.request.url,
                                       data=self.request.post_data, headers=self.request.headers, auth=auth,
                                       allow_redirects=allow_redirects, compress=compress,
                                       proxy=proxy, proxy_auth=proxy_auth, timeout=timeout) as resp:
                body = await resp.read()
                response_headers = []
                for name, value in resp.headers.items():
                    response_headers.append({"name": name, "value": value})
                await self.fulfill(response_code=resp.status, body=body,
                                   response_headers=response_headers, response_phrase=None)

    async def continue_request(self, headers: typing.List[typing.Dict[str, str]] = None, method: str = None,
                               post_data: typing.Union[str, bytes] = None, url: str = None,
                               intercept_response: bool = None):
        """
        continue the request.
        You might use :func:`InterceptedRequest.fulfill <selenium_driverless.scripts.network_interceptor.InterceptedRequest.fulfill>`
        to provide a response body

        :param headers: array of {"name":name, "value":value},  mind header order
        :param method: the method of the request
        :param post_data: the binary post data to provide
        :param url: the url to continue the request with, change not observable by the page
        :param intercept_response: overrides response interception behavior for this request
        """
        if self._done:
            raise RequestDoneException(self)
        params = {"requestId": self.id}

        if isinstance(post_data, str):
            post_data = post_data.encode("utf-8")
        if post_data:
            post_data = base64.b64encode(post_data).decode("ascii")
        if headers:
            params["headers"] = headers
        if method:
            params["method"] = method
        if post_data:
            params["postData"] = post_data
        if url:
            params["url"] = url
        if not (intercept_response is None):
            params["interceptResponse"] = intercept_response
        try:
            await self.target.execute_cdp_cmd("Fetch.continueRequest", params)
        except CDPError as e:
            if not (e.code == -32602 and e.message == 'Invalid InterceptionId.'):
                raise e
        self._done = True

    async def continue_response(self, response_headers: typing.List[typing.Dict[str, str]] = None,
                                binary_response_headers: bytes = None,
                                response_code: int = None, response_phrase: str = None):
        """
        continue the response.
        You might use :func:`By <selenium_driverless.scripts.network_interceptor.InterceptedRequest.fulfill>`
        to provide a response body

        :param response_code: response code
        :param binary_response_headers:  headers as a \0-separated series of name: value pairs, treated as base64 encode if a string is passed,
        :param response_headers: array of {"name":name, "value":value},  mind header order
        :param response_phrase: response phrase (``"OK"`` for ``response_code=200``)
        """
        if self._done:
            raise RequestDoneException(self)
        if binary_response_headers:
            binary_response_headers = base64.b64encode(binary_response_headers).decode("ascii")
        params = {"requestId": self.id}
        if response_headers:
            params["responseHeaders"] = response_headers
        if binary_response_headers:
            params["binaryResponseHeaders"] = binary_response_headers
        if response_code:
            params["responseCode"] = response_code
        if response_phrase:
            params["responsePhrase"] = response_phrase
        try:
            await self.target.execute_cdp_cmd("Fetch.continueResponse", params)
        except CDPError as e:
            if not (e.code == -32602 and e.message == 'Invalid InterceptionId.'):
                # request cancelled due to reload for example
                raise e
        self._done = True

    async def resume(self):
        """
        continue the request or response
        doesn't raise id the request is canceled or already done
        """
        if not self._done:
            try:
                await self.continue_request()
            except websockets.ConnectionClosedError:
                pass

    async def fail_request(self, error_reason: typing.Literal["Failed", "Aborted", "TimedOut", "AccessDenied", "ConnectionClosed", "ConnectionReset", "ConnectionRefused", "ConnectionAborted", "ConnectionFailed", "NameNotResolved", "InternetDisconnected", "AddressUnreachable", "BlockedByClient", "BlockedByResponse"]):
        """
        fail the request or response

        :param error_reason: the specified reason for the request failing
        """
        if self._done:
            raise RequestDoneException(self)
        params = {"requestId": self.id}
        if error_reason:
            params["errorReason"] = error_reason
        try:
            await self.target.execute_cdp_cmd("Fetch.failRequest", params)
        except CDPError as e:
            if not (e.code == -32602 and e.message == 'Invalid InterceptionId.'):
                raise e
        self._done = True

    async def fulfill(self, response_code: int, binary_response_headers: str = None,
                      body: typing.Union[str, bytes] = None,
                      response_headers: typing.List[typing.Dict[str, str]] = None, response_phrase: str = None):
        """
        fulfill the request or response

        :param response_code: response code
        :param body: the response body
        :param binary_response_headers:  headers as a \0-separated series of name: value pairs, treated as base64 encode if a string is passed,
        :param response_headers: array of {"name":name, "value":value},  mind header order
        :param response_phrase: response phrase (``"OK"`` for ``response_code=200``)
        """
        if self._done:
            raise RequestDoneException(self)
        params = {"requestId": self.id}

        if response_headers is None:
            if self.response_headers:
                response_headers = self.response_headers
        if response_code is None:
            if self.response_status_code:
                response_code = self.response_status_code
        if response_phrase is None:
            if self.response_status_text != "":
                # can't be empty
                response_phrase = self.response_status_text
        if isinstance(body, str):
            body = body.encode("utf-8")
        if body:
            body = base64.b64encode(body).decode("ascii")
        if isinstance(binary_response_headers, bytes):
            binary_response_headers = base64.b64encode(binary_response_headers).decode("ascii")

        if response_code:
            params["responseCode"] = response_code
        if binary_response_headers:
            params["binaryResponseHeaders"] = binary_response_headers
        if body:
            params["body"] = body
        if response_headers:
            params["responseHeaders"] = response_headers
        if response_phrase:
            params["responsePhrase"] = response_phrase
        try:
            await self.target.execute_cdp_cmd("Fetch.fulfillRequest", params)
        except CDPError as e:
            if not (e.code == -32602 and e.message == 'Invalid InterceptionId.'):
                raise e
        self._done = True

    def __repr__(self):
        return self.params.__repr__()


class InterceptedAuth:
    def __init__(self, params, target):
        self._params = params
        self._target = target
        self._done = False
        self._stage = None
        self._is_redirect = None
        self._body = False
        self._request = None
        self._auth_challenge = None
        self.timeout = 10

    @property
    def request(self) -> Request:
        """the Request, for which auth is required"""
        if self._request is None:
            self._request = Request(self._params["request"], self.target)
        return self._request

    @property
    def id(self) -> str:
        """the ``Fetch.RequestId``"""
        return self.params["requestId"]

    @property
    def frame_id(self) -> str:
        """the ``Page.FrameId`` from which the request has been initiated"""
        return self._params["frameId"]

    @property
    def params(self) -> dict:
        """the parameters from `Fetch.authRequired <https://chromedevtools.github.io/devtools-protocol/tot/Fetch/#event-authRequired>`_ as a dict"""
        return self._params

    @property
    def target(self) -> typing.Union[Target, BaseTarget]:
        """the target"""
        return self._target

    @property
    def resource_type(self) -> str:
        """
        the `Network.ResourceType`
        """
        return self._params["resourceType"]

    @property
    def auth_challenge(self) -> AuthChallenge:
        """
        the AuthChallenge
        """
        if self._auth_challenge is None:
            self._auth_challenge = AuthChallenge(self._params["request"], self.target)
        return self._auth_challenge

    async def continue_auth(self, response: typing.Literal["Default", "CancelAuth", "ProvideCredentials"] = "Default",
                            username: str = None, password: str = None):
        """
        continue the auth

        :param response: "Default" by default, automatically set to "ProvideCredentials", if username or password specified
        :param username: username for the auth
        :param password: password for the auth
        """
        if self._done:
            raise RequestDoneException(self)

        if username or password:
            response = "ProvideCredentials"
        challenge_response = {"response": response}
        if username:
            challenge_response["username"] = username
        if password:
            challenge_response["password"] = password
        try:
            await self.target.execute_cdp_cmd("Fetch.continueWithAuth",
                                              {"requestId": self.id, "authChallengeResponse": challenge_response},
                                              timeout=self.timeout)
            self._done = True
        except CDPError as e:
            if e.code == -32000 and e.message == 'Invalid state for continueInterceptedRequest':
                raise AuthAlreadyHandledException(self)
            else:
                raise e

    async def resume(self):
        """
        continue the auth
        doesn't raise id the request is canceled or already done
        """
        if not self._done:
            try:
                await self.continue_auth()
            except (AuthAlreadyHandledException, websockets.ConnectionClosedError):
                pass

    async def cancel(self):
        """
        cancel the auth
        """
        await self.continue_auth(response="CancelAuth")

    def __repr__(self):
        return self.params.__repr__()


RequestCallbackType = typing.Callable[[InterceptedRequest], typing.Awaitable[None]]
AuthCallbackType = typing.Callable[[InterceptedRequest], typing.Awaitable[None]]


class NetworkInterceptor:
    on_request: RequestCallbackType
    on_response: RequestCallbackType
    on_auth: AuthCallbackType

    def __init__(self, target: typing.Union[Chrome, Target], on_request: RequestCallbackType = None,
                 on_response: RequestCallbackType = None, on_auth: AuthCallbackType = None,
                 patterns: typing.Union[PatternsType, typing.List[RequestPattern]] = None, intercept_auth: bool = False,
                 bypass_service_workers: bool = False):
        """
        :param target: the Target or Driver, on which requests get intercepted
        :param on_request: onRequest callback
        :param on_response: onResponse callback
        :param on_auth: onAuth callback
        :param patterns: the request patterns to intercept
        :param intercept_auth: whether to intercept authentification
        :param bypass_service_workers: whether to bypass service workers for a single Target
        """
        if patterns is None:
            patterns = [RequestPattern.AnyRequest, RequestPattern.AnyResponse]

        _patters = []
        for pattern in patterns:
            if isinstance(pattern, RequestPattern):
                pattern = pattern.value
            _patters.append(pattern)

        self._iter_callbacks: typing.Dict[str, typing.List[asyncio.Future]] = {}

        if isinstance(target, Chrome):
            driver = target
            target = driver.base_target
        else:
            # noinspection PyProtectedMember
            driver = target._driver

        # noinspection PyUnusedLocal
        async def blank_callback(data):
            pass

        if on_request is None:
            on_request = blank_callback
        if on_response is None:
            on_response = blank_callback
        if on_auth is None:
            on_auth = blank_callback

        self._driver = driver
        self._started = False
        self._bypass_service_workers = bypass_service_workers
        self.on_request = on_request
        self.on_response = on_response
        self.on_auth = on_auth
        self._target = target
        self._patterns = _patters
        self._intercept_auth = intercept_auth

    async def __aenter__(self):
        if not self._started:
            await self.target.execute_cdp_cmd("Fetch.enable",
                                              cmd_args={"patterns": self._patterns,
                                                        "handleAuthRequests": self._intercept_auth})
            await self.target.add_cdp_listener("Fetch.authRequired", self._paused_handler)
            if self._bypass_service_workers:
                await self.target.execute_cdp_cmd("Network.setBypassServiceWorker",
                                                  {"bypass": self._bypass_service_workers})
            await self.target.add_cdp_listener("Fetch.requestPaused", self._paused_handler)
            self._started = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._bypass_service_workers:
            await self.target.execute_cdp_cmd("Network.setBypassServiceWorker", {"bypass": False})
        try:
            await self.target.execute_cdp_cmd("Fetch.disable")
        except CDPError as e:
            if not (e.code == -32000 and e.message == 'Fetch domain is not enabled'):
                raise e
        try:
            await self.target.remove_cdp_listener("Fetch.requestPaused", self._paused_handler)
        except ValueError:
            pass  # ValueError: list.remove(x): x not in list
        try:
            await self.target.remove_cdp_listener("Fetch.authRequired", self._paused_handler)
        except ValueError:
            pass

    async def _paused_handler(self, params: dict):
        if "authChallenge" in params.keys():
            request = InterceptedAuth(params, self.target)
        else:
            request = InterceptedRequest(params, self.target)
        coro = []
        for _id, val in list(self._iter_callbacks.items()):
            fut, done = val
            try:
                fut.set_result(request)
            except asyncio.InvalidStateError:
                pass
            else:
                coro.append(done)
            finally:
                del self._iter_callbacks[_id]
        if coro:
            await asyncio.gather(*coro)

        if isinstance(request, InterceptedRequest):
            if request.stage == RequestStages.Response:
                try:
                    await self.on_response(request)
                except Exception as e:
                    await request.resume()
                    raise e
            else:
                try:
                    await self.on_request(request)
                except Exception as e:
                    await request.resume()
                    raise e
        else:
            await self.on_auth(request)
        await request.resume()

    def __aiter__(self) -> typing.AsyncIterator[typing.Union[InterceptedRequest, InterceptedAuth]]:
        """
        iterate using ``async for`` over requests

        **Example**

        .. code-block:: Python

            from selenium_driverless.scripts.network_interceptor import InterceptedRequest, RequestStages

            # ... some code
            async for data in interceptor:
                url = data.request.url
                if isinstance(data, InterceptedRequest):
                    data.stage == RequestStages.Request:
                        print("Request:"+url)
                    else:
                        print("Response:"+url)
                else:
                    print("Authentification:"+url)


        .. warning::
            iterations should virtually take zero time, you might use ``asyncio.ensure_future`` where possible

        """

        async def _iter():
            while True:
                fut, done = asyncio.Future(), asyncio.Future()
                self._iter_callbacks[uuid.uuid4().hex] = [fut, done]
                res = await fut
                yield res
                try:
                    done.set_result(1)
                except asyncio.InvalidStateError:
                    pass

        return _iter()

    @property
    def patterns(self) -> PatternsType:
        """patters to intercept"""
        return self._patterns

    @property
    def target(self) -> typing.Union[Target, BaseTarget]:
        """the Target, on which requests get intercepted"""
        return self._target
