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

import asyncio
import functools
import inspect
import logging
import random
import sys
import typing as t
from types import SimpleNamespace, TracebackType

from selenium_driverless.pycdp.base import IEventLoop

_T = t.TypeVar('_T')


class LoggerMixin:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = logging.getLogger(f'pycdp.{type(self).__name__}')


class ContextLoggerMixin(LoggerMixin):
    logging.getLogger('pycdp.ContextLoggerMixin')  # just create the logger

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = logging.LoggerAdapter(
            logging.getLogger(f'pycdp.ContextLoggerMixin.{type(self).__name__}'),
            {}
        )
        self.set_logger_context(realname=f'pycdp.{type(self).__name__}')

    def set_logger_context(self, **context):
        self._logger.extra.update(context)


class DoneTask:

    def done(self):
        return True

    def cancel(self):
        pass


class Retry(LoggerMixin):

    def __init__(self,
                 func,
                 exception_class: t.Collection[BaseException],
                 loop: IEventLoop,
                 *,
                 retries: int = 1,
                 on_error: t.Union[str, t.Callable[[], t.Awaitable[None]]] = None,
                 log_errors: bool = False
                 ):
        super().__init__()
        self._func = func
        self._errors = exception_class
        self._loop = loop
        self._retries = retries
        self._log_errors = log_errors
        self._on_error_cb = on_error

    async def __call__(self, *args, **kwargs):
        context = self._create_call_context()
        for i in range(self._retries + 1):
            try:
                return await self._func(*args, **kwargs)
            except self._errors as e:  # type: ignore
                if i == self._retries:
                    raise e
                if self._log_errors:
                    if self._logger.getEffectiveLevel() == logging.DEBUG:
                        self._logger.exception(
                            'error in %s() (attempt %d of %d, at %s:%d), retrying:',
                            self._func.__qualname__,
                            i + 1,
                            self._retries,
                            self._get_appcode_frame(sys.exc_info()[-1]).tb_frame.f_code.co_filename,
                            self._get_appcode_frame(sys.exc_info()[-1]).tb_lineno
                        )
                    else:
                        self._logger.error(
                            'error in %s() (attempt %d of %d, at %s:%d), retrying: %s',
                            self._func.__qualname__,
                            i + 1,
                            self._retries,
                            self._get_appcode_frame(sys.exc_info()[-1]).tb_frame.f_code.co_filename,
                            self._get_appcode_frame(sys.exc_info()[-1]).tb_lineno,
                            repr(e)
                        )
                await self._on_error(args[0] if len(args) > 0 else None, context)

    def _create_call_context(self):
        return None

    async def _on_error(self, instance, context):
        if self._on_error_cb is not None:
            if isinstance(self._on_error_cb, str):
                cb = getattr(instance, self._on_error_cb)
            else:
                cb = self._on_error_cb
            result = cb()
            if inspect.isawaitable(result):
                await result

    def _get_appcode_frame(self, exc: TracebackType):
        """Returns traceback frame from code outside this file."""
        while True:
            if exc.tb_next is None or exc.tb_frame.f_code.co_filename != __file__:
                return exc
            exc = exc.tb_next


class DelayedRetry(Retry):

    def __init__(self, delay: float, delay_growth: float, max_delay: float, **kwargs):
        super().__init__(**kwargs)
        self._delay = delay
        self._delay_growth = delay_growth
        self._max_delay = max_delay

    async def _on_error(self, instance, context):
        await super()._on_error(instance, context)
        delay = self._get_delay(context)
        if delay > 0.0:
            await self._loop.sleep(delay)
        self._grow_delay(context)

    def _create_call_context(self):
        return SimpleNamespace(current_delay=self._delay)

    def _get_delay(self, context):
        return min(context.current_delay, self._max_delay)

    def _grow_delay(self, context):
        try:
            context.current_delay *= self._delay_growth
        except OverflowError:
            context.current_delay = self._max_delay


class RandomDelayedRetry(DelayedRetry):

    def _create_call_context(self):
        return SimpleNamespace(current_delay=self._delay[1])

    def _get_delay(self, context):
        return random.uniform(self._delay[0], super()._get_delay(context))


def retry_on(
        *exception_class: t.Type[BaseException],
        loop: IEventLoop,
        retries: int = 1,
        delay: t.Union[float, t.Tuple[float, float]] = 0.0,
        delay_growth: float = 1.0,
        max_delay: int = 600,
        log_errors: bool = False,
        on_error: str = None,
):
    if not isinstance(delay, (float, tuple)):
        raise TypeError('delay must be a float or a tuple of 2 floats')

    def deco_factory(func):
        if type(delay) is float:
            if delay <= 0.0:
                decorator = Retry(
                    func,
                    exception_class,
                    retries=retries,
                    log_errors=log_errors,
                    on_error=on_error,
                    loop=loop
                )
            else:
                decorator = DelayedRetry(
                    delay,
                    delay_growth,
                    max_delay,
                    func=func,
                    exception_class=exception_class,
                    retries=retries,
                    log_errors=log_errors,
                    on_error=on_error,
                    loop=loop
                )
        else:
            decorator = RandomDelayedRetry(
                delay,
                delay_growth,
                max_delay,
                func=func,
                exception_class=exception_class,
                retries=retries,
                log_errors=log_errors,
                on_error=on_error,
                loop=loop
            )

        @functools.wraps(func)
        async def func_wrapper(*args, **kwargs):
            return await decorator(*args, **kwargs)

        return func_wrapper

    return deco_factory


class Closable(LoggerMixin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._closing = False
        self._closed = False
        self._close_event = asyncio.Event()

    @property
    def is_open(self):
        return not self._closing and not self._closed

    @property
    def closed(self):
        return self._closed

    async def wait_closed(self):
        await self._close_event.wait()

    async def close(self):
        if self._closed:
            return
        elif self._closing:
            await self._close_event.wait()
        else:
            self._logger.debug('closing...')
            self._closing = True
            try:
                await self._close()
            finally:
                self._closing = False
                self._closed = True
                self._logger.info('closed.')
                self._close_event.set()

    async def _close(self):
        pass


class WorkerBase(Closable):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._started = False
        self._closing = False
        self._closed = True

    @property
    def is_open(self):
        return self._started and super().is_open

    def start(self):
        if self._started:
            raise RuntimeError('already started')
        if not self._closed:
            raise RuntimeError('expected worker to be closed on startup')
        self._logger.info('start working')
        self._started = True
        self._closing = False
        self._closed = False
        self._startup()

    def _startup(self) -> None:
        pass

    async def close(self):
        await super().close()
        self._started = False


class SubtaskSpawner(Closable):
    """Keeps track of spanwed async tasks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._subtasks: t.List[asyncio.Task] = []
        self._exception_waiter = asyncio.get_running_loop().create_future()
        self._exception_handlers = 0

    async def wait_exception(self):
        """Catch first exception raised from any subtask of this spawner."""
        try:
            self._exception_handlers += 1
            await asyncio.shield(self._exception_waiter)
        finally:
            self._exception_handlers -= 1

    async def wait_subtasks(self):
        """Wait all *current* subtasks to finish and return their result even if it's an exception."""
        return await asyncio.gather(*(asyncio.shield(task) for task in self._subtasks), return_exceptions=True)

    async def _close(self):
        await super()._close()
        self._cancel_subtasks()
        self._exception_waiter.cancel()
        self._subtasks.clear()

    def _cancel_subtasks(self):
        for task in self._subtasks:
            task.cancel()

    def _create_subtask(self, coro: t.Union[t.Coroutine[t.Any, t.Any, _T], 'asyncio.Future[_T]'],
                        name=None) -> 'asyncio.Future[_T]':
        if not self.is_open:
            raise RuntimeError(f'{type(self).__name__} is not open')
        if inspect.iscoroutine(coro):
            task = asyncio.create_task(coro, name=name)
        else:
            task = coro
        task.add_done_callback(self._check_subtask_result)
        self._subtasks.append(task)
        return task

    def _check_subtask_result(self, task: asyncio.Task):
        try:
            task.result()
        except asyncio.CancelledError as exc:
            self._logger.debug('the subtask %s was cancelled', repr(task))
        except BaseException as exc:
            if self._exception_handlers > 0:
                if not self._exception_waiter.done():
                    self._logger.debug(
                        'firing the exception handler for %s from subtask %s',
                        type(exc).__name__, repr(task)
                    )
                    self._exception_waiter.set_exception(exc)
                else:
                    self._logger.exception(
                        'an error happened in the subtask %s but exception handler was already fired:',
                        repr(task)
                    )
            else:
                self._logger.exception('an error happened in the subtask %s:', repr(task))


class Worker(SubtaskSpawner, WorkerBase):
    """Daemon object that does some king of work."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._subworkers: t.List[Worker] = []

    def _startup(self) -> None:
        super()._startup()
        if self._exception_waiter.done():
            self._exception_waiter = asyncio.get_running_loop().create_future()

    async def close_on_exception(self, exc: Exception):
        await self.close()

    def _start_subworker(self, worker: 'Worker'):
        self._create_subtask(self._watch_subworker(worker))
        worker.start()

    async def _watch_subworker(self, worker: 'Worker'):
        self._subworkers.append(worker)
        try:
            await worker.wait_exception()
        finally:
            self._subworkers.remove(worker)

    async def _close(self):
        await super()._close()
        await asyncio.gather(*(worker.close() for worker in self._subworkers if worker.is_open))


class SingleTaskWorker(Worker):

    def _startup(self):
        super()._startup()
        self._start_run_task()

    def _start_run_task(self):
        self._create_subtask(self._run())

    async def _run(self):
        raise NotImplementedError
