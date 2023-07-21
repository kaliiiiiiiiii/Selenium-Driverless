import copy
import json
import logging
import re
import sys


class PayloadMixin:
    @classmethod
    def build_send_payload(cls, method: str, params: dict):
        return {
            "method": ".".join([cls.__name__, method]),
            "params": {k: v for k, v in params.items() if v is not None}
        }

    @classmethod
    def convert_payload(cls, types: dict):
        def convert(result: dict):
            """

            :param result:
            :return:
            """
            types_ = copy.copy(types)
            for name, val in result.items():
                try:
                    expected_ = types_.pop(name)
                    expected_type_ = expected_['class']
                except KeyError:
                    raise KeyError('name %s not in expected payload of %s' % (name, types))
                if issubclass(expected_type_, ChromeTypeBase):
                    result[name] = expected_type_(**val)
                elif re.match(r'.*Id$', name) and isinstance(val, str):
                    result[name] = expected_type_(val)
                elif not isinstance(val, expected_type_):
                    raise ValueError('%s is not expected type %s, instead is %s' % (val, expected_type_, val))
            for rn, rv in types_.items():
                if not rv.get('optional', False):
                    raise ValueError('expected payload param "%s" is missing!' % rn)
            return result
        return convert


log = logging.getLogger(__name__)


class BaseEvent:
    js_name = 'chromewhipBaseEvent'
    hashable = []
    is_hashable = False

    def hash_(self):
        hashable_params = {}
        for k, v in self.__dict__.items():
            if k in self.hashable:
                hashable_params[k] = v
            else:
                try:
                    hashable_params['%sId' % k] = v.id
                except KeyError:
                    pass
                except AttributeError:
                    # TODO: make better, fails for event that has 'timestamp` as a param
                    pass
        serialized_id_params = ','.join(['='.join([p, str(v)]) for p, v in hashable_params.items()])
        h = '{}:{}'.format(self.js_name, serialized_id_params)
        log.debug('generated hash = %s' % h)
        return h


# TODO: how do
def json_to_event(payload) -> BaseEvent:
    try:
        prot_name, js_event = payload['method'].split('.')
    except KeyError:
        log.error('invalid event JSON, must have a "method" key')
        return None
    except ValueError:
        log.error('invalid method name "%s", must contain a module and event joined with a "."' % payload['method'])
        return None
    module_name = 'chromewhip.protocol.%s' % prot_name.lower()
    try:
        prot_module = sys.modules[module_name]
    except KeyError:
        msg = '"%s" is not available in sys.modules!' % module_name
        log.error(msg)
        raise KeyError(msg)
    py_event_name = '{}{}Event'.format(js_event[0].upper(), js_event[1:])
    event_cls = getattr(prot_module, py_event_name)
    try:
        result = event_cls(**payload['params'])
    except TypeError as e:
        raise TypeError('%s unable to deserialise: %s' % (event_cls.__name__, e))
    return result


class ChromeTypeBase:

    def to_dict(self):
        return self.__dict__


class ChromewhipJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, BaseEvent):
            return {'method': obj.js_name, 'params': obj.__dict__}

        if isinstance(obj, ChromeTypeBase):
            return obj.__dict__

        return json.JSONEncoder.default(self, obj)
