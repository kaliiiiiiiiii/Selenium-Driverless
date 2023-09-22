class JSRemoteObj:
    pass


class JSObject(JSRemoteObj, dict):
    def __init__(self):
        JSRemoteObj.__init__(self)

    def __getattr__(self, k):
        # noinspection PyBroadException
        try:
            return self[k]
        except:
            return self.__getitem__(k)

    def __setattr__(self, k, v):
        self[k] = v


class JSArray(list, JSRemoteObj):
    def __init__(self):
        JSRemoteObj.__init__(self)


class JSWindow(JSRemoteObj):
    def __init__(self, context: str):
        self.__context__ = context
        JSRemoteObj.__init__(self)


class JSBigInt(int):
    pass


class JSRegExp(str):
    pass


class JSDate(str):
    pass


class JSSymbol(JSRemoteObj):
    def __init__(self):
        JSRemoteObj.__init__(self)


class JSFunction(JSRemoteObj):
    def __init__(self):
        JSRemoteObj.__init__(self)


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


class JSWeakMap(JSRemoteObj):
    def __init__(self):
        JSRemoteObj.__init__(self)


class JSSet(set):
    pass

class JSError(JSRemoteObj):
    def __init__(self):
        JSRemoteObj.__init__(self)


class JSUnserializable(JSRemoteObj):
    def __init__(self, _type, value, obj_id: str = None, obj_path: str = None):
        super().__init__(obj_id=obj_id, obj_path=obj_path)
        self._value = value
        self._type = _type

    @property
    def value(self):
        return self._value

    @property
    def type(self):
        return self._type

    def __repr__(self):
        return f'Type: "{self.type}", Value: "{self.value}"'


def parse_deep(deep: dict):
    # structures
    _type = deep.get("type")
    _value = deep.get("value")
    if _type == "array":
        _res = JSArray()
        for idx, _deep in enumerate(_value):
            _res.append(parse_deep(_deep))
        return _res
    elif _type == "object":
        _res = JSObject()
        for key, value in _value:
            _res.__setattr__(key, parse_deep(value))
        return _res

    # non-json properties
    elif _type == "bigint":
        return JSBigInt(_value)
    elif _type == "regexp":
        return JSRegExp(_value["pattern"])
    elif _type == "date":
        return JSDate(_value)
    elif _type == "symbol":
        return JSSymbol()
    elif _type == "function":
        return JSFunction()
    elif _type == "map":
        _map = JSMap()
        for key, value in _value:
            key = parse_deep(key)
            _map.set(key, parse_deep(value))
        return _map
    elif _type == "set":
        _set = set()
        for value in enumerate(_value):
            value = parse_deep(value)
            _set.add(value)
        return _set
    elif _type == "weakmap":
        return JSWeakMap()
    elif _type == "error":
        return JSError()
    elif _type == "proxy":
        return JSUnserializable(_type, _value)
    elif _type == "promise":
        return JSUnserializable(_type, _value)
    elif _type == "typedarray":
        return JSUnserializable(_type, _value)
    elif _type == "arraybuffer":
        return JSUnserializable(_type, _value)
    elif _type == "node":
        return JSUnserializable(_type, _value)
    elif _type == "window":
        return JSWindow(context=_value.get("context"))
    elif _type == "generator":
        return JSUnserializable(_type, _value)

    # low-level types
    elif _type in ["number", "string"]:
        return _value
    elif _type in ["undefined", "null"]:
        return None
    elif _type == "boolean":
        return JSUnserializable(_type, _value)

    # non-parsable
    else:
        return JSUnserializable(_type, _value)
