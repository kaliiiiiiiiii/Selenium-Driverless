# The MIT License (MIT)
#
# Copyright (c) 2018 Hyperion Gray
# Copyright (c) 2022 Heraldo Lucena
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import os
import shutil
import signal
import subprocess
import tempfile
import typing as t
import warnings
from io import TextIOWrapper

from pycdp.utils import LoggerMixin


class BrowserLauncher(LoggerMixin):

    def __init__(
            self,
            *,
            binary: str,
            profile: str = None,
            keep_profile: bool = True,
            headless: bool = False,
            locale: str = None,
            timezone: str = None,
            proxy: str = None,
            window_width: int = None,
            window_height: int = None,
            initial_url: str = None,
            extensions: t.List[str] = [],
            args: t.List[str] = None,
            log: bool = True
    ):
        super().__init__()
        self._binary = binary
        self._headless = headless
        self._locale = locale
        self._timezone = timezone
        self._proxy = proxy
        self._window_width = window_width
        self._window_height = window_height
        self._extensions = extensions
        self._initial_url = initial_url
        self._args = args
        self._log = log
        self._process: subprocess.Popen = None
        if profile is None:
            self._keep_profile = False
            self._profile = None
        else:
            self._profile = profile
            self._keep_profile = keep_profile
        self._logfile: TextIOWrapper = None

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def locale(self):
        return self._locale

    @property
    def timezone(self):
        return self._timezone

    def launch(self):
        if self._process is not None: raise RuntimeError('already launched')
        if self._log:
            self._logfile = open(f'{self.__class__.__name__.lower()}.log', 'a')
            stdout = stderr = self._logfile
            self._logger.debug('redirecting output to %s.log', self.__class__.__name__.lower())
        else:
            stdout = stderr = subprocess.DEVNULL
            self._logger.debug('redirecting output to subprocess.DEVNULL')
        if self._profile is None:
            self._profile = tempfile.mkdtemp()
            self._configure_profile()
        cmd = self._build_launch_cmdline()
        self._logger.debug('launching %s', cmd)
        self._process = subprocess.Popen(
            cmd,
            env=self._build_launch_env(),
            stdin=subprocess.PIPE,
            stdout=stdout,
            stderr=stderr,
            text=True,
            close_fds=True,
            preexec_fn=os.setsid if os.name == 'posix' else None,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        try:
            self._logger.debug('waiting launch finish...')
            returncode = self._process.wait(1)
        except subprocess.TimeoutExpired:
            self._logger.debug('launch finished')

    def kill(self, timeout: float = 3.0):
        if self._process is not None:
            if os.name == 'posix':
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            else:
                self._process.terminate()
            try:
                self._process.wait(timeout)
            except subprocess.TimeoutExpired:
                if os.name == 'posix':
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                else:
                    self._process.kill()
            self._process = None
            if self._logfile is not None and not self._logfile.closed:
                self._logfile.close()
            if not self._keep_profile:
                shutil.rmtree(self._profile, ignore_errors=True)

    def _build_launch_cmdline(self) -> t.List[str]:
        raise NotImplementedError

    def _build_launch_env(self):
        env = os.environ.copy()
        if os.name == 'posix':
            if self._timezone is not None:
                env['TZ'] = self._timezone
            if self._locale is not None:
                env['LANGUAGE'] = self._locale
        return env

    def _configure_profile(self):
        pass

    def __del__(self):
        if self._process is not None:
            warnings.warn('A BrowserLauncher instance has not closed with .kill(), it will leak')


class ChromeLauncher(BrowserLauncher):

    def _build_launch_cmdline(self) -> t.List[str]:
        cmd = [
            self._binary,
            f'--window-size={self._window_width},{self._window_height}' if self._window_width is not None and self._window_height is not None else '--start-maximized',
            f'--user-data-dir={self._profile}' if self._profile is not None else '',
            '--no-first-run',
            '--no-service-autorun',
            '--no-default-browser-check',
            '--homepage=about:blank',
            '--no-pings',
            '--password-store=basic',
            '--disable-infobars',
            '--disable-breakpad',
            '--disable-component-update',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-background-networking',
            '--disable-dev-shm-usage'
        ]
        if os.name == 'posix':
            cmd.append('--enable-logging')
            cmd.append('--v=2')
        if self._headless:
            cmd.append('--headless')
            cmd.append('--disable-gpu')
        if self._proxy is not None:
            cmd.append(f'--proxy-server={self._proxy}')
        if len(self._extensions) > 0:
            cmd.append(f"--load-extension={','.join(str(path) for path in self._extensions)}")
        if os.name == 'nt' and self._locale is not None:
            cmd.append(f'--lang={self._locale}')
        if self._args is not None:
            cmd.extend(self._args)
        if self._initial_url is not None:
            cmd.append(self._initial_url)
        return cmd
