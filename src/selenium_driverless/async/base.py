# Copyright 2017 Robert Charles Smith
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# modified by kaliiiiiiiiii | Aurin Aegerter

# https://stackoverflow.com/questions/30155138/how-can-i-write-asyncio-coroutines-that-optionally-act-as-regular-functions
import asyncio


class SyncAdder(type):
    """ A metaclass which adds synchronous version of coroutines.

    This metaclass finds all coroutine functions defined on a class
    and adds a synchronous version with a '_s' suffix appended to the
    original function name.

    """
    def __new__(cls, clsname, bases, dct, **kwargs):
        new_dct = {}
        for name,val in dct.items():
            # Make a sync version of all coroutine functions
            if asyncio.iscoroutinefunction(val):
                meth = cls.sync_maker(name)
                syncname = '{}_s'.format(name)
                meth.__name__ = syncname
                meth.__qualname__ = '{}.{}'.format(clsname, syncname)
                new_dct[syncname] = meth
        dct.update(new_dct)
        return super().__new__(cls, clsname, bases, dct)

    @staticmethod
    def sync_maker(func):
        def sync_func(self, *args, **kwargs):
            meth = getattr(self, func)
            return asyncio.get_event_loop().run_until_complete(meth(*args, **kwargs))
        return sync_func
