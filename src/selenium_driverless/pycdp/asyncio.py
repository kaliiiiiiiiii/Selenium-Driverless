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

# edited by kaliiiiiiiiii | Aurin Aegerter

from __future__ import annotations

import asyncio
import itertools
import json
import typing as t
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager

from aiohttp import ClientSession
from aiohttp.client import ClientWebSocketResponse
from aiohttp.client_exceptions import (
    ClientResponseError, ClientConnectorError, ClientConnectionError, ServerDisconnectedError
)
from aiohttp.http_websocket import WSMsgType, WSCloseCode

from selenium_driverless.pycdp import cdp
from selenium_driverless.pycdp.base import IEventLoop
from selenium_driverless.pycdp.exceptions import *
from selenium_driverless.pycdp.utils import ContextLoggerMixin, LoggerMixin, SingleTaskWorker, retry_on

T = t.TypeVar('T')


class AsyncIOEventLoop(IEventLoop):

    async def sleep(self, delay: float) -> None:
        await asyncio.sleep(delay)


loop = AsyncIOEventLoop()

_CLOSE_SENTINEL = object


class CDPEventListener:

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue
        self._closed = False

    @property
    def closed(self):
        return self._closed

    def put(self, elem: dict):
        if self._closed: raise CDPEventListenerClosed
        self._queue.put_nowait(elem)

    def close(self):
        self._closed = True
        try:
            self._queue.put_nowait(_CLOSE_SENTINEL)
        except asyncio.QueueFull:
            pass

    async def __aiter__(self):
        try:
            while not self._closed:
                elem = await self._queue.get()
                if elem is _CLOSE_SENTINEL:
                    return
                yield elem
        finally:
            self._closed = True

    def __str__(self) -> str:
        return f'{self.__class__.__name__}(buffer={self._queue.qsize()}/{self._queue.maxsize}, closed={self._closed})'


class CDPBase(LoggerMixin):
    """
    Contains shared functionality between the CDP connection and session.
    """

    def __init__(self, ws: ClientWebSocketResponse = None, session_id=None, target_id=None):
        super().__init__()
        self._listeners: t.Dict[type, t.Set[CDPEventListener]] = defaultdict(set)
        self._id_iter = itertools.count()
        self._inflight_cmd: t.Dict[int, t.Tuple[t.Generator[dict, dict, t.Any], asyncio.Future]] = {}
        self._session_id = session_id
        self._target_id = target_id
        self._ws = ws

    @property
    def session_id(self) -> cdp.target.SessionID:
        return self._session_id

    async def execute(self, cmd: t.Generator[dict, dict, T]) -> T:
        """
        Execute a command on the server and wait for the result.

        :param cmd: any CDP command
        :returns: a CDP result
        """
        cmd_id = next(self._id_iter)
        cmd_response = asyncio.get_running_loop().create_future()
        self._inflight_cmd[cmd_id] = cmd, cmd_response
        request = next(cmd)
        request['id'] = cmd_id
        if self._session_id:
            request['sessionId'] = self._session_id
        self._logger.debug('sending command %r', request)
        request_str = json.dumps(request)
        try:
            try:
                await self._ws.send_str(request_str)
            except ConnectionResetError as e:
                del self._inflight_cmd[cmd_id]
                raise CDPConnectionClosed(e.args[0]) from e
            return await cmd_response
        except asyncio.CancelledError:
            if cmd_id in self._inflight_cmd:
                del self._inflight_cmd[cmd_id]
            raise

    def listen(self, *event_types: t.Type[T], buffer_size=100) -> t.AsyncIterator[T]:
        """Return an async iterator that iterates over events matching the
        indicated types."""
        receiver = CDPEventListener(asyncio.Queue(buffer_size))
        for event_type in event_types:
            self._listeners[event_type].add(receiver)
        return receiver.__aiter__()

    @asynccontextmanager
    async def wait_for(self, event_type: t.Type[T]) -> t.AsyncGenerator[T, None]:
        """
        Wait for an event of the given type and return it.

        This is an async context manager, so you should open it inside an async
        with block. The block will not exit until the indicated event is
        received.
        """
        async for event in self.listen(event_type, buffer_size=2):
            yield event
            return

    @contextmanager
    def safe_wait_for(self, event_type: t.Type[T]) -> t.Generator[t.Awaitable[T], None]:
        """
        Wait for an asynchronous event. This context manager yields a awaitable that should be
        awaited to receive the event.
        
        Use this context manager to register an event listener before performing the action which will
        trigger the event like a page navigation, it avoids the race conditions of wait_for().
        """
        aevent = asyncio.create_task(self._async_wait_for(event_type))
        try:
            yield aevent
        finally:
            if not aevent.done():
                aevent.cancel()

    async def _async_wait_for(self, event_type: t.Type[T]) -> T:
        async for event in self.listen(event_type, buffer_size=2):
            return event

    def close_listeners(self):
        for listener in itertools.chain.from_iterable(self._listeners.values()):
            listener.close()
        self._listeners.clear()

    def _handle_data(self, data):
        """
        Handle incoming WebSocket data.

        :param dict data: a JSON dictionary
        """
        if 'id' in data:
            self._handle_cmd_response(data)
        else:
            self._handle_event(data)

    def _handle_cmd_response(self, data):
        '''
        Handle a response to a command. This will set an event flag that will
        return control to the task that called the command.

        :param dict data: response as a JSON dictionary
        '''
        cmd_id = data['id']
        try:
            cmd, event = self._inflight_cmd.pop(cmd_id)
        except KeyError:
            self._logger.debug('got a message with a command ID that does not exist: %s', data)
            return
        if 'error' in data:
            # If the server reported an error, convert it to an exception and do
            # not process the response any further.
            event.set_exception(CDPBrowserError(data['error']))
        else:
            # Otherwise, continue the generator to parse the JSON result
            # into a CDP object.
            try:
                cmd.send(data['result'])
                event.set_exception(CDPInternalError("the command's generator function did not exit when expected!"))
            except StopIteration as e:
                event.set_result(e.value)

    def _handle_event(self, data):
        '''
        Handle an event.

        :param dict data: event as a JSON dictionary
        '''
        event = cdp.util.parse_json_event(data)
        self._logger.debug('dispatching event %s', event)
        to_remove = set()
        for listener in self._listeners[type(event)]:
            try:
                listener.put(event)
            except asyncio.QueueFull:
                self._logger.warning('event %s dropped because listener %s queue is full', type(event), listener)
            except CDPEventListenerClosed:
                to_remove.add(listener)
        self._listeners[type(event)] -= to_remove
        self._logger.debug('event dispatched')


class CDPConnection(CDPBase, SingleTaskWorker):
    '''
    Contains the connection state for a Chrome DevTools Protocol server.

    CDP can multiplex multiple "sessions" over a single connection. This class
    corresponds to the "root" session, i.e. the implicitly created session that
    has no session ID. This class is responsible for reading incoming WebSocket
    messages and forwarding them to the corresponding session, as well as
    handling messages targeted at the root session itself.

    You should generally call the :func:`open_cdp()` instead of
    instantiating this class directly.
    '''

    def __init__(self, debugging_url: str, http_client: ClientSession):
        super().__init__()
        self._debugging_url = debugging_url.rstrip('/')
        self._http_client = http_client
        self._wsurl: str = None
        self._ws_context = None
        self._sessions: t.Dict[str, CDPSession] = {}

    @property
    def closed(self) -> bool:
        return self._ws.closed

    @property
    def had_normal_closure(self) -> bool:
        return self._ws.close_code == WSCloseCode.OK

    @retry_on(
        ClientConnectorError, asyncio.TimeoutError,
        retries=10, delay=3.0, delay_growth=1.3, log_errors=True, loop=loop
    )
    async def connect(self):
        if self._ws is not None: raise RuntimeError('already connected')
        if self._wsurl is None:
            if self._debugging_url.startswith('http://'):
                async with self._http_client.get(f'{self._debugging_url}/json/version') as resp:
                    if resp.status != 200:
                        raise ClientResponseError(
                            resp.request_info,
                            resp.history,
                            status=resp.status,
                            message=resp.reason,
                            headers=resp.headers
                        )
                    self._wsurl = (await resp.json())['webSocketDebuggerUrl']
            elif self._debugging_url.startswith('ws://'):
                self._wsurl = self._debugging_url
            else:
                raise ValueError('bad debugging URL scheme')
        self._ws = await self._http_client.ws_connect(self._wsurl, compress=15, autoping=True,
                                                      autoclose=True).__aenter__()

    def add_session(self, session_id: str, target_id: str) -> CDPSession:
        if session_id is self._sessions:
            return self._sessions[session_id]
        session = CDPSession(self._ws, session_id, target_id)
        self._sessions[session_id] = session
        return session

    def remove_session(self, session_id: str):
        if session_id in self._sessions:
            self._sessions.pop(session_id).close()

    async def connect_session(self, target_id: cdp.target.TargetID) -> 'CDPSession':
        '''
        Returns a new :class:`CDPSession` connected to the specified target.
        '''
        session_id = await self.execute(cdp.target.attach_to_target(target_id, True))
        session = CDPSession(self._ws, session_id, target_id)
        self._sessions[session_id] = session
        return session

    async def _run(self):
        while True:
            message = await self._ws.receive()
            if message.type == WSMsgType.TEXT:
                try:
                    data = json.loads(message.data)
                except json.JSONDecodeError:
                    raise CDPBrowserError({
                        'code': -32700,
                        'message': 'Client received invalid JSON',
                        'data': message
                    })
                if 'sessionId' in data:
                    session_id = cdp.target.SessionID(data['sessionId'])
                    try:
                        session = self._sessions[session_id]
                    except KeyError:
                        self._logger.debug(f'received message for unknown session: {data}')
                        continue
                    session._handle_data(data)
                else:
                    self._handle_data(data)
            elif message.type == WSMsgType.CLOSE or message.type == WSMsgType.CLOSING or message.type == WSMsgType.CLOSED:
                return
            elif message.type == WSMsgType.ERROR:
                raise message.data
            else:
                await self._ws.close(code=WSCloseCode.UNSUPPORTED_DATA)
                raise CDPConnectionClosed('received non text frame from remote peer')

    async def _close(self):
        try:
            await super()._close()
            for session in self._sessions.values():
                session.close()
            self._sessions.clear()
            self.close_listeners()
            if self._ws is not None and not self._ws.closed:
                await self._ws.close()
        finally:
            await self._http_client.close()


class CDPSession(CDPBase, ContextLoggerMixin):
    '''
    Contains the state for a CDP session.

    Generally you should not instantiate this object yourself; you should call
    :meth:`CdpConnection.open_session`.
    '''

    def __init__(self, ws: ClientWebSocketResponse, session_id: cdp.target.SessionID, target_id: cdp.target.TargetID):
        super().__init__(ws, session_id, target_id)
        self._dom_enable_count = 0
        self._dom_enable_lock = asyncio.Lock()
        self._page_enable_count = 0
        self._page_enable_lock = asyncio.Lock()
        self.set_logger_context(extra_name=session_id)

    @asynccontextmanager
    async def dom_enable(self):
        '''
        A context manager that executes ``dom.enable()`` when it enters and then
        calls ``dom.disable()``.

        This keeps track of concurrent callers and only disables DOM events when
        all callers have exited.
        '''
        async with self._dom_enable_lock:
            self._dom_enable_count += 1
            if self._dom_enable_count == 1:
                await self.execute(cdp.dom.enable())

        yield

        async with self._dom_enable_lock:
            self._dom_enable_count -= 1
            if self._dom_enable_count == 0:
                await self.execute(cdp.dom.disable())

    @asynccontextmanager
    async def page_enable(self):
        '''
        A context manager that executes ``page.enable()`` when it enters and
        then calls ``page.disable()`` when it exits.

        This keeps track of concurrent callers and only disables page events
        when all callers have exited.
        '''
        async with self._page_enable_lock:
            self._page_enable_count += 1
            if self._page_enable_count == 1:
                await self.execute(cdp.page.enable())

        yield

        async with self._page_enable_lock:
            self._page_enable_count -= 1
            if self._page_enable_count == 0:
                await self.execute(cdp.page.disable())

    def close(self):
        if len(self._inflight_cmd) > 0:
            exc = CDPSessionClosed()
            for (_, event) in self._inflight_cmd.values():
                if not event.done():
                    event.set_exception(exc)
            self._inflight_cmd.clear()
        self.close_listeners()


@retry_on(ClientConnectionError, ServerDisconnectedError, retries=10, delay=3.0, delay_growth=1.3, log_errors=True,
          loop=loop)
async def connect_cdp(url: str) -> CDPConnection:
    '''
    Connect to the browser specified by debugging ``url``.

    This connection is not automatically closed! You can either use the connection
    object as a context manager (``async with conn:``) or else call ``await
    conn.aclose()`` on it when you are done with it.
    '''
    http = ClientSession()
    cdp_conn = CDPConnection(url, http)
    try:
        await cdp_conn.connect()
        cdp_conn.start()
    except:
        await http.close()
        raise
    return cdp_conn
