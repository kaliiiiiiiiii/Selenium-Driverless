from selenium_driverless import webdriver
import asyncio

global driver

user = "user1"
psw = "password"
host = "http://my_proxy.com:5000"

response = {"response": "ProvideCredentials", "username": user, "password": psw}


async def auth_callback(data):
    global driver
    if data["authChallenge"]["origin"] == f"{host}":
        await driver.base_target.execute_cdp_cmd("Fetch.continueWithAuth",
                                                 {"requestId": data["requestId"], "authChallengeResponse": response})
    else:
        await driver.base_target.execute_cdp_cmd("Fetch.continueWithAuth",
                                                 {"requestId": data["requestId"],
                                                  "authChallengeResponse": {"response": "Default"}})
    print(data)


async def on_request(params):
    global driver
    await driver.base_target.execute_cdp_cmd("Fetch.continueRequest", {"requestId": params['requestId']})


async def main():
    global driver

    options = webdriver.ChromeOptions()
    options.add_argument(f"--proxy-server={host}")
    async with webdriver.Chrome(options=options) as driver:
        await driver.base_target.execute_cdp_cmd("Fetch.enable",
                                                 {"handleAuthRequests": True, "patterns":
                                                     [{"urlPattern": f"*"}]})
        await driver.base_target.add_cdp_listener("Fetch.authRequired", auth_callback)
        await driver.base_target.add_cdp_listener("Fetch.requestPaused", on_request)

        await driver.get("https://nordvpn.com/uk/what-is-my-ip/", wait_load=False)

        # the loops has to keep running for auth testing
        x = True
        while x:
            await asyncio.sleep(10)


asyncio.run(main())
