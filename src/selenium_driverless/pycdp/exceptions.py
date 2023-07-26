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


class CDPError(Exception):
    pass


class CDPBrowserError(CDPError):
    ''' This exception is raised when the browser's response to a command
    indicates that an error occurred. '''

    def __init__(self, obj):
        self.code: int = obj['code']
        self.message: str = obj['message']
        self.detail = obj.get('data')

    def __str__(self):
        return 'BrowserError<code={} message={}> {}'.format(self.code,
                                                            self.message, self.detail)


class CDPConnectionClosed(CDPError):
    ''' Raised when a public method is called on a closed CDP connection. '''

    def __init__(self, reason):
        '''
        Constructor.
        :param reason:
        :type reason: wsproto.frame_protocol.CloseReason
        '''
        self.reason = reason

    def __repr__(self):
        ''' Return representation. '''
        return '{}<{}>'.format(self.__class__.__name__, self.reason)


class CDPSessionClosed(CDPError):
    pass


class CDPInternalError(CDPError):
    ''' This exception is only raised when there is faulty logic in TrioCDP or
    the integration with PyCDP. '''


class CDPEventListenerClosed(CDPError):
    pass
