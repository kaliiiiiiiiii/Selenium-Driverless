import asyncio
import json
from selenium_driverless import webdriver
from selenium_driverless.scripts.network_interceptor import NetworkInterceptor, InterceptedRequest, InterceptedAuth, \
    RequestPattern, RequestStages


async def on_request(data: InterceptedRequest):
    if data.request.url == "https://httpbin.org/post":
        await data.continue_request(url="https://httpbin.org/basic-auth/user/pass", intercept_response=True)


async def main():
    async with webdriver.Chrome(max_ws_size=2 ** 30) as driver:

        async with NetworkInterceptor(driver, on_request=on_request, patterns=[RequestPattern.AnyRequest],
                                      intercept_auth=True) as interceptor:

            asyncio.ensure_future(driver.get("https://httpbin.org/post", wait_load=False))
            async for data in interceptor:
                if data.request.url == "https://httpbin.org/basic-auth/user/pass":
                    if isinstance(data, InterceptedAuth):
                        # iteration should take virtually zero time, as that would block other requests
                        asyncio.ensure_future(data.continue_auth(username="user", password="pass"))
                    elif data.stage == RequestStages.Response:
                        print(json.loads(await data.body))
                        break


asyncio.run(main())
