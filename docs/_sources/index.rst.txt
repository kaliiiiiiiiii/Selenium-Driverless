Documentation Selenium-Driverless
===============================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

.. note::
    this is not complete yet at all:)
    some methods aren't documented yet properly



Usage
==================
.. code-block:: Python

   from selenium_driverless import webdriver
    from selenium_driverless.types.by import By
    import asyncio


    async def main():
        options = webdriver.ChromeOptions()
        async with webdriver.Chrome(options=options) as driver:
            await driver.get('http://nowsecure.nl#relax', wait_load=True)
            await driver.sleep(0.5)
            await driver.wait_for_cdp("Page.domContentEventFired", timeout=15)

            # wait 10s for elem to exist
            elem = await driver.find_element(By.XPATH, '/html/body/div[2]/div/main/p[2]/a', timeout=10)
            await elem.click(move_to=True)

            alert = await driver.switch_to.alert
            print(alert.text)
            await alert.accept()

            print(await driver.title)


    asyncio.run(main())


API
--------

.. toctree::
    :glob:
    :maxdepth: 2

    api/*


