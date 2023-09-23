import asyncio

from selenium_driverless.types.webelement import WebElement
from selenium_driverless.sync.webelement import WebElement as SyncWebElement
from selenium_driverless.types import RemoteObject


class JSRemoteObj:
    def __init__(self, obj_id: str, target, context_id: str):
        super().__init__()
        remote_obj = None
        if obj_id:
            remote_obj = RemoteObject(obj_id=obj_id, target=target, context_id=context_id)
        super().__setattr__("__remote_obj__", remote_obj)
        super().__setattr__("__context_id__", context_id)
        super().__setattr__("__obj_id__", obj_id)

    def __repr__(self):
        # noinspection PyUnresolvedReferences
        return f'{self.__class__.__name__}(obj_id={self.__obj_id__}, context_id="{self.__context_id__}")'

    # noinspection PyUnresolvedReferences
    def __eq__(self, other):
        if isinstance(other, JSRemoteObj) and other.__obj_id__ and self.__obj_id__:
            return other.__obj_id__.split(".")[0] == self.__obj_id__.split(".")[0]
        return super().__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        # noinspection PyUnresolvedReferences
        return hash(f"{self.__obj_id__}{self.__class__}")


class JSObject(JSRemoteObj, dict):
    def __init__(self, obj_id: str, context_id: str, target, description: str = None, class_name: str = None,
                 sub_type: str = None):
        JSRemoteObj.__init__(self, obj_id, target, context_id)
        dict.__init__(self)
        super().__setattr__("__description__", description)
        super().__setattr__("__class_name__", class_name)
        super().__setattr__("__sub_type__", sub_type)

    def __getattr__(self, k):
        # noinspection PyBroadException
        try:
            return self[k]
        except:
            return self.__getitem__(k)

    def __setattr__(self, k, v):
        self[k] = v

    def __repr__(self):
        return f'{self.__class__.__name__}(description={self.__description__}, sub_type={self.__sub_type__}, class_name={self.__class_name__}, obj_id="{self.__obj_id__}", context_id={self.__context_id__})'

    def __hash__(self):
        # noinspection PyUnresolvedReferences
        return hash(f"{self.__obj_id__}{self.__class__}")


class JSArray(list, JSRemoteObj):
    def __init__(self, obj_id: str, target, context_id: str):
        JSRemoteObj.__init__(self, obj_id, target, context_id)

    def __hash__(self):
        # noinspection PyUnresolvedReferences
        return hash(f"{self.__obj_id__}{self.__class__}")


class JSWindow(JSRemoteObj):
    def __init__(self, context: str, obj_id: str, target, context_id: str):
        self.__context__ = context
        JSRemoteObj.__init__(self, obj_id, target, context_id)


class JSBigInt(int):
    pass


class JSRegExp(str):
    pass


class JSDate(str):
    pass


class JSSymbol(JSRemoteObj):
    def __init__(self, obj_id: str, target, context_id: str):
        JSRemoteObj.__init__(self, obj_id, target, context_id)


class JSFunction(JSRemoteObj):
    def __init__(self, obj_id: str, target, context_id: str, description: str):
        self.__description__ = description
        super().__init__(obj_id, target, context_id)

    async def __call__(self, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        return await self.__remote_obj__.execute_script(f"return obj(...arguments)", *args, **kwargs)

    def __repr__(self):
        # noinspection PyUnresolvedReferences
        return f'{self.__class__.__name__}("{self.__description__}", obj_id="{self.__obj_id__}", context_id={self.__context_id__})'


class JSMapException(Exception):
    # from https://stackoverflow.com/a/71705517
    # modified by kaliiiiiiiiii
    pass


class JSMap(dict, JSRemoteObj):
    # from https://stackoverflow.com/a/71705517
    # modified by kaliiiiiiiiii

    def __init__(self, *args):
        values = [self.__create_element(key, value) for key, value in args]
        self.__values__ = values
        super().__init__()

    def __setitem__(self, key, value):
        self.set(key, value)

    def __getitem__(self, key):
        return self.get(key)

    def __len__(self):
        return len(self.__values__)

    def __delitem__(self, key):
        keys = self.keys()

        if key in keys:
            index = keys.index(key)
            del self.__values__[index]

    def clear(self):
        self.__values__ = []

    def copy(self):
        return self.__values__.copy()

    def has_key(self, k):
        return k in self.keys()

    def update(self, *args, **kwargs):
        if kwargs:
            raise JSMapException(f"no kwargs allowed in '{self.__class__.__name__}.update' method")
        for key, value in args:
            self[key] = value

        return self.__values__

    def __repr__(self) -> str:
        return repr(self.__values__)

    @classmethod
    def __create_element(cls, key, value):
        return {"key": key, "value": value}

    def set(self, key, value):
        keys = self.keys()

        if key in keys:
            index = keys.index(key)
            self.__values__[index] = self.__create_element(key, value)
        else:
            self.__values__.append(self.__create_element(key, value))

        return self.__values__

    def keys(self) -> list:
        return [dict_key_value["key"] for dict_key_value in self.__values__]

    def values(self):
        return [value["value"] for value in self.__values__]

    def items(self):
        return [(dict_key_value["key"], dict_key_value["value"]) for dict_key_value in self.__values__]

    def pop(self, key, default=None):
        keys = self.keys()

        if key in keys:
            index = keys.index(key)
            value = self.__values__.pop(index)["value"]
        else:
            value = default

        return value

    def get(self, key, default=None):
        keys = self.keys()

        if key in keys:
            index = keys.index(key)
            value = self.__values__[index]["value"]
        else:
            value = default

        return value

    def __iter__(self):
        return iter(self.keys())

    def __hash__(self):
        # noinspection PyUnresolvedReferences
        return hash(f"{self.__obj_id__}{self.__class__}")


class JSWeakMap(JSRemoteObj):
    def __init__(self, obj_id: str, target, context_id: str):
        JSRemoteObj.__init__(self, obj_id, target, context_id)


class JSSet(JSRemoteObj, set):
    def __init__(self, obj_id: str, target, context_id: str):
        set.__init__(self)
        JSRemoteObj.__init__(self, obj_id, target, context_id)


class JSError(JSRemoteObj):
    def __init__(self, obj_id: str, target, context_id: str):
        JSRemoteObj.__init__(self, obj_id, target, context_id)


class JSProxy(JSRemoteObj):
    def __init__(self, obj_id: str, target, context_id: str):
        JSRemoteObj.__init__(self, obj_id, target, context_id)


class JSPromise(JSRemoteObj):
    def __init__(self, obj_id: str, target, context_id: str):
        JSRemoteObj.__init__(self, obj_id, target, context_id)


class JSTypedArray(JSRemoteObj):
    def __init__(self, obj_id: str, target, context_id: str):
        JSRemoteObj.__init__(self, obj_id, target, context_id)


class JSArrayBuffer(JSRemoteObj):
    def __init__(self, obj_id: str, target, context_id: str):
        JSRemoteObj.__init__(self, obj_id, target, context_id)


class JSIterator(JSFunction):
    def __init__(self, obj_id: str, target, context_id: str, description: str):
        super().__init__(obj_id, target, context_id=context_id, description=description)


class JSNodeList(JSArray):
    def __init__(self, obj_id: str, target, class_name: str, context_id: str):
        super().__init__(obj_id, target, context_id)
        super().__setattr__("__class_name__", class_name)

    def __repr__(self):
        # noinspection PyUnresolvedReferences
        return f'{self.__class__.__name__}("{self.__class_name__}",obj_id={self.__obj_id__}, context_id={self.__context_id__})'


class JSUnserializable(JSRemoteObj):
    def __init__(self, _type, value, context_id: str, target, obj_id: str = None, description: str = None,
                 sub_type: str = None,
                 class_name: str = None):
        super().__init__(obj_id=obj_id, target=target, context_id=context_id)
        self._value = value
        self._type = _type
        self._description = description
        self._sub_type = sub_type
        self._class_name = class_name

    @property
    def value(self):
        return self._value

    @property
    def type(self):
        return self._type

    @property
    def description(self):
        return self._description

    @property
    def sub_type(self):
        return self._sub_type

    @property
    def class_name(self):
        return self._class_name

    def __repr__(self):
        # noinspection PyUnresolvedReferences
        return f'{self.__class__.__name__}(type="{self.type}",description="{self.description}", sub_type="{self.sub_type}", class_name="{self.class_name}", value={self.value}, obj_id="{self.__obj_id__}")'


async def parse_deep(deep: dict, target, subtype: str = None, class_name: str = None, description: str = None,
                     value=None, obj_id: str = None, loop: asyncio.AbstractEventLoop = None, context_id: str = None):
    if not deep:
        if value:
            return value
        else:
            return JSUnserializable("IdOnly", None, target=target, obj_id=obj_id, context_id=context_id)

    # special types
    if class_name == 'XPathResult':
        elems = JSNodeList(obj_id=obj_id, target=target, class_name=class_name, context_id=context_id)
        obj = await RemoteObject(target=target, obj_id=obj_id, check_existence=False)
        if await obj.execute_script("return [7].includes(obj.resultType)", serialization="json", execution_context_id=context_id):
            for idx in range(await obj.execute_script("return obj.snapshotLength", serialization="json", execution_context_id=context_id)):
                elems.append(await obj.execute_script("return obj.snapshotItem(arguments[0])", idx,
                                                      serialization="deep", execution_context_id=context_id))
            return elems
    if class_name in ['NodeList', 'HTMLCollection']:
        elems = []
        obj = await RemoteObject(target=target, obj_id=obj_id, check_existence=False)
        for idx in range(int(description[-2])):
            elems.append(await obj.execute_script("return this[arguments[0]]", idx, serialization="deep", execution_context_id=context_id))
        return elems

    # structures
    _type = deep.get("type")
    _value = deep.get("value")
    if _type == "array":
        _res = JSArray(obj_id=obj_id, target=target, context_id=context_id)
        for idx, _deep in enumerate(_value):
            _res.append(await parse_deep(_deep, target))
        return _res
    elif _type == "object":
        _res = JSObject(obj_id=obj_id, target=target, description=description, sub_type=subtype, class_name=class_name, context_id=context_id)
        for key, value in _value:
            _res.__setattr__(key, await parse_deep(value, target))
        return _res

    # non-json types
    elif _type == "bigint":
        return JSBigInt(_value)
    elif _type == "regexp":
        return JSRegExp(_value["pattern"])
    elif _type == "date":
        return JSDate(_value)
    elif _type == "symbol":
        return JSSymbol(obj_id=obj_id, target=target, context_id=context_id)
    elif _type == "function":
        return JSFunction(obj_id=obj_id, target=target, description=description, context_id=context_id)
    elif _type == "map":
        _map = JSMap()
        for key, value in _value:
            key = await parse_deep(key, target)
            _map.set(key, await parse_deep(value, target))
        return _map
    elif _type == "set":
        _set = JSSet(obj_id=obj_id, target=target, context_id=context_id)
        for value in _value:
            value = await parse_deep(value, target)
            _set.add(value)
        return _set
    elif _type == "weakmap":
        return JSWeakMap(obj_id=obj_id, target=target, context_id=context_id)
    elif _type == "error":
        return JSError(obj_id=obj_id, target=target, context_id=context_id)
    elif _type == "proxy":
        return JSProxy(obj_id, target=target, context_id=context_id)
    elif _type == "promise":
        return JSPromise(obj_id, target=target, context_id=context_id)
    elif _type == "typedarray":
        return JSTypedArray(obj_id, target=target, context_id=context_id)
    elif _type == "arraybuffer":
        return JSArrayBuffer(obj_id, target=target, context_id=context_id)
    elif _type == "node":
        if loop:
            return await SyncWebElement(backend_node_id=_value.get('backendNodeId'), target=target, loop=loop,
                                        check_existence=False, class_name=class_name, context_id=context_id)
        else:
            return await WebElement(backend_node_id=_value.get('backendNodeId'), target=target, loop=loop,
                                    check_existence=False, class_name=class_name, context_id=context_id)
    elif _type == "window":
        return JSWindow(context=_value.get("context"), obj_id=obj_id, target=target, context_id=context_id)
    elif _type == "generator":
        return JSUnserializable(_type, _value, target=target, obj_id=obj_id, context_id=context_id, description=description)

    # low-level types
    elif _type in ["number", "string", "boolean"]:
        return _value
    elif _type in ["undefined", "null"]:
        return None

    # non-serializable
    else:
        return JSUnserializable(_type, _value, target=target, obj_id=obj_id, description=description, sub_type=subtype,
                                class_name=class_name, context_id=context_id)
