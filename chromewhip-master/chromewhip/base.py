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
