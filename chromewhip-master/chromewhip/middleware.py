import json
import traceback
import pprint

from aiohttp import web

from chromewhip.chrome import ChromewhipException


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
