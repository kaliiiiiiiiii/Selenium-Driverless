from selenium_driverless.async_.webdriver import ChromeDriver as BaseChrome

import typing
import types


class Chrome(BaseChrome):
    def __exit__(
            self,
            exc_type: typing.Optional[typing.Type[BaseException]],
            exc: typing.Optional[BaseException],
            traceback: typing.Optional[types.TracebackType],
    ):
        self.quit()
