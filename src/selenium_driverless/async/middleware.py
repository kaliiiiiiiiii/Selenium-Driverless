# Copyright 2017 Robert Charles Smith
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# modified by kaliiiiiiiiii | Aurin Aegerter

import json
import traceback

from aiohttp import web

from .chrome import ChromewhipException


def json_error(message):
    # return web.Response(
    #     body=json.dumps({'error': message}).encode('utf-8'),
    #     content_type='application/json')
    # return web.Response(text=pprint.pformat({'error': message}))
    return web.Response(text=json.dumps({'error': message}, indent=4))


async def error_middleware(app, handler):
    async def middleware_handler(request):
        try:
            response = await handler(request)
            if response.status != 200:
                return json_error(response.message)
            return response
        except web.HTTPException as ex:
            return json_error(ex.reason)
        except ChromewhipException as ex:
            return json_error(ex.args[0])
        except Exception as ex:
            verbose_tb = traceback.format_exc()
            return json_error(verbose_tb)

    return middleware_handler
