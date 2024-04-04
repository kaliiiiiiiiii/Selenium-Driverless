from selenium_driverless.webdriver import Chrome
from selenium_driverless.types.target import Target
import typing


async def fetch(url: str, driver: typing.Union[Chrome, Target],
                method: typing.Literal["GET", "POST", "HEAD", "PUT", "DELETE", "CONNECT", "OPTIONS", "TRACE", None] = "GET",
                headers: typing.Dict[str, str] = None, body: str = None,
                mode: typing.Literal["cors", "no-cors", "same-origin", None] = None,
                credentials: typing.Literal["omit", "same-origin", "include"] = None,
                cache:typing.Literal["default", "no-store", "reload", "no-cache", "force-cache", "only-if-cached"]=None,
                redirect:typing.Literal["follow", "error"] = None, referrer:str=None,
                referrer_policy:typing.Literal["no-referrer", "no-referrer-when-downgrade", "same-origin", "origin", "strict-origin", "origin-when-cross-origin", "strict-origin-when-cross-origin", "unsafe-url"]=None,
                integrity:str=None, keepalive=None, priority:typing.Literal["high", "low", "auto", None]="high", timeout:float=20):
    # see https://developer.mozilla.org/en-US/docs/Web/API/fetch
    options = {}
    if method:
        options["method"] = method
    if headers:
        options["headers"] = headers
    if body:
        options["body"] = body
    if mode:
        options["mode"] = mode
    if credentials:
        options["credentials"] = credentials
    if cache:
        options["cache"] = cache
    if redirect:
        options["redirect"] = redirect
    if referrer:
        options["referrer"] = referrer
    if referrer_policy:
        options["referrerPolicy"] = referrer_policy
    if integrity:
        options["integrity"] = integrity
    if keepalive:
        options["keepalive"] = keepalive
    if priority:
        options["priority"] = priority

    script = """
        function buffer2hex (buffer) {
            return [...new Uint8Array (buffer)]
                .map (b => b.toString (16).padStart (2, "0"))
                .join ("");
        }
        
        function headers2dict(headers){
            var my_dict = {};
            for (var pair of headers.entries()) {
                    my_dict[pair[0]] = pair[1]};
            return my_dict}
        
        async function get(url, options){
            var response = await fetch(url, options);
            var buffer = await response.arrayBuffer()
            var hex = buffer2hex(buffer)
            var res = {
                    "HEX":hex,
                    "headers":headers2dict(response.headers),
                    "ok":response.ok,
                    "status_code":response.status,
                    "redirected":response.redirected,
                    "status_text":response.statusText,
                    "type":response.type,
                    "url":response.url
                    };
            console.log(res)
            return res;
        }
        return await get(arguments[0], arguments[1])
    """
    result = await driver.eval_async(script, url, options, unique_context=True, timeout=timeout)
    result["body"] = bytes.fromhex(result["HEX"])
    del result["HEX"]
    return result


async def xhr(driver: typing.Union[Chrome, Target], url: str, method: typing.Literal["GET", "POST", "PUT", "DELETE"] = "GET",
              user: str = None, password: str = None, with_credentials: bool = True, mime_type: str = "text/xml",
              extra_headers: typing.Dict[str, str] = None,
              timeout: float = 30):
    if extra_headers is None:
        extra_headers = {}
    script = """
    function makeRequest(withCredentials, mimeType, extraHeaders, ...args) {
        return new Promise(function (resolve, reject) {
            try{
                let xhr = new XMLHttpRequest();

                if(!(args[3])){args[3] = null};
                if(!(args[4])){args[4] = null};
                xhr.overrideMimeType(mimeType);

                xhr.open(...args);
                Object.keys(extraHeaders).forEach(function(key) {
                    xhr.setRequestHeader(key, extraHeaders[key])
                });
                xhr.withCredentials = withCredentials;

                xhr.onload = function () {
                    resolve(xhr)
                };
                xhr.onerror = function () {
                    reject(new Error("XHR failed"));
                };
                xhr.send();
            }catch(e){reject(e)}
        });
    };

    var xhr =  await makeRequest(...arguments);
    data = {
        status: xhr.status,
        response: xhr.response,
        responseText:xhr.responseText,
        responseType:xhr.responseType,
        responseURL:xhr.responseURL,
        responseXML:xhr.responseXML,
        statusText:xhr.statusText,
        responseHeaders:xhr.getAllResponseHeaders()

    };
    return data
    """
    data = await driver.eval_async(script, with_credentials, mime_type, extra_headers, method, url, True, user,
                                   password,
                                   timeout=timeout, unique_context=True)

    # parse headers
    headers = data['responseHeaders']
    if headers == "null":
        _headers = {}
    else:
        headers = headers.split("\r\n")
        _headers = {}
        for header in headers:
            header = header.split(': ')
            if len(header) == 2:
                key, value = header
                _headers[key] = value
    data['responseHeaders'] = _headers

    # todo: parse different response types
    return data
