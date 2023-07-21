import time
import unittest
from selenium.webdriver.common.by import By  # locate elements


def return_driver():
    from selenium_profiles import driver as mydriver
    from selenium_profiles.profiles import profiles

    mydriver = mydriver()
    profile = profiles.Windows()

    global driver
    driver = mydriver.start(profile, uc_driver=False)
    return driver


async def at_request(event, connection):
    global cdp_listener
    session, devtools = connection.session, connection.devtools
    cdp_listener.print_event(event)
    body = await cdp_listener.get_response_body(event.request_id)

    rc_type = event.resource_type.name.lower()
    if rc_type == "xhr" and body[0]:
        decoded = cdp_listener.decode_body(body[0], event)
        if '/api/headers' in event.request.url:
            decoded['cloudfront-viewer-city'] = "Welcome to Hell!"
        encoded = cdp_listener.encode_body(decoded)
        body = (encoded, body[1])
        return devtools.fetch.fulfill_request(request_id=event.request_id, response_code=event.response_status_code,
                                              body=body[0], response_headers=event.response_headers)
    else:
        return devtools.fetch.continue_response(request_id=event.request_id)


class Driver(unittest.TestCase):
    def test_headers(self):
        from selenium_interceptor.interceptor import cdp_listener
        my_platform = "Test_Platform"
        driver = return_driver()
        cdp_listener = cdp_listener(driver=driver)
        cdp_listener.specify_headers({"sec-ch-ua-platform": my_platform})
        thread = cdp_listener.start_threaded(
            listener={"listener": cdp_listener.requests, "at_event": cdp_listener.modify_headers})

        driver.get('https://modheader.com/headers?product=ModHeader')
        time.sleep(4)
        driver.refresh()
        driver.get('https://modheader.com/headers?product=ModHeader')
        time.sleep(2)
        platform = driver.find_element(By.XPATH,
                                       '/html/body/div[1]/main/div[1]/div/div/div/table[1]/tbody/tr[19]/td[2]').accessible_name

        time.sleep(1)
        cdp_listener.terminate_all()
        self.assertEqual(platform, my_platform)  # add assertion here

    def test_response_mod(self):
        from selenium_interceptor.interceptor import cdp_listener

        my_city = "Welcome to Hell!"

        driver = return_driver()
        global cdp_listener
        cdp_listener = cdp_listener(driver=driver)
        thread = cdp_listener.start_threaded(
            listener={"listener": cdp_listener.responses, "at_event": at_request})

        driver.get('https://modheader.com/headers?product=ModHeader')
        time.sleep(4)
        driver.find_element(By.XPATH, '/html/body/div[1]/main/div[1]/div/div/div/div/button').click()
        time.sleep(4)
        city = driver.find_element(By.XPATH,
                                   '/html/body/div[1]/main/div[1]/div/div/div/table[1]/tbody/tr[10]/td[2]').accessible_name

        time.sleep(1)
        cdp_listener.terminate_all()
        self.assertEqual(city, my_city)


if __name__ == '__main__':
    unittest.main()
