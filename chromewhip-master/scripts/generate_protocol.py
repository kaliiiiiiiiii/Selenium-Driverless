import json
import os.path
import re
import sys

from jinja2 import Template

# TODO: circular dependency below
# PACKAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
#
# sys.path.insert(0, PACKAGE_DIR)
#
# from chromewhip.helpers import camelize

FULL_CAP_WORDS = ['url', 'dom', 'css', 'html']


def camelize(string):
    words = string.split('_')
    result = words[0]
    for w in words[1:]:
        w = w.upper() if w in FULL_CAP_WORDS else w.title()
        result += w
    return result

camel_pat = re.compile(r'([A-Z]+)')

template_fp = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/protocol.py.j2'))
output_dir_fp = os.path.abspath(os.path.join(os.path.dirname(__file__), '../chromewhip/protocol/'))
browser_json_fp = ('browser', os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/browser_protocol.json')))
js_json_fp = ('js', os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/js_protocol.json')))
test_script_fp = os.path.abspath(os.path.join(os.path.dirname(__file__), './check_generation.py'))


# https://stackoverflow.com/questions/17156078/converting-identifier-naming-between-camelcase-and-underscores-during-json-seria



JS_PYTHON_TYPES = {
    'string': 'str',
    'number': 'float',
    'integer': 'int',
}


def set_py_type(type_obj, type_ids_set):
    type_ = type_obj['type']
    id_ = type_obj['id']
    if re.match(r'.*Id', id_) and id_[:2] in type_ids_set:
        new_type_ = 'py_chrome_identifier'
    elif type_ == 'array':
        item_type = type_obj['items'].get('$ref') or type_obj['items'].get('type')
        try:
            new_type_ = '[%s]' % JS_PYTHON_TYPES[item_type]
        except KeyError:
            new_type_ = '[%s]' % item_type
    elif type_ == 'object':
        if not type_obj.get('properties'):
            new_type_ = 'dict'
        else:
            new_type_ = 'object'
    elif type_ in JS_PYTHON_TYPES.keys():
        new_type_ = JS_PYTHON_TYPES[type_]
    else:
        raise ValueError('type "%s" is not recognised, check type data = %s' % (type_, type_obj))
    type_obj['type'] = new_type_

# import autopep8
processed_data = {}
hashable_objs_per_prot = {}
for fpd in [js_json_fp, browser_json_fp]:
    pname, fp = fpd
    data = json.load(open(fp))

    # first run
    hashable_objs = set()
    for domain in data['domains']:

        for event in domain.get('events', []):
            event['py_class_name'] = event['name'][0].upper() + camelize(event['name'][1:]) + 'Event'

        # 12 Jul 9:37am - wont need this for now as have enhanced Id type
        # for cmd in domain.get('commands', []):
        #     for r in cmd.get('returns', []):
        #         # convert to non id
        #         if r.get('$ref', ''):
        #             r['$ref'] = re.sub(r'Id$', '', r['$ref'])

        for type_obj in domain.get('types', []):
            # we assume all type ids that contain `Id` are an alias for a built in type
            if any(filter(lambda p: p['name'] == 'id', type_obj.get('properties', []))):
                hashable_objs.add(type_obj['id'])


        # shorten references to drop domain if part of same module
        # for command in domain.get('commands', []):
        #     for parameter in command.get('parameters', []):
        #         ref = parameter.get('$ref')
        #         if ref and ref.split('.')[0] == domain['name']:
        #             print('modifying command "%s"' % '.'.join([domain['name'], command['name']]))
        #             ref

    hashable_objs_per_prot[pname] = hashable_objs
    processed_data[pname] = data

# second run
for k, v in processed_data.items():
    hashable_objs = hashable_objs_per_prot[k]
    for domain in v['domains']:
        for type_obj in domain.get('types', []):
            # convert to richer, Python compatible types
            set_py_type(type_obj, hashable_objs)

        for event in domain.get('events', []):
            p_names = [p['name'] for p in event.get('parameters', [])]
            p_refs = [(p['name'], p['$ref']) for p in event.get('parameters', []) if p.get('$ref')]
            h_names = set(filter(lambda n: 'id' in n or 'Id' in n, p_names))
            for pn, pr in p_refs:
                if pr in hashable_objs:
                    h_names.add(pn + 'Id')
            event['hashable'] = list(h_names)
            event['is_hashable'] = len(event['hashable']) > 0

# finally write to file
t = Template(open(template_fp).read(), trim_blocks=True, lstrip_blocks=True)
test_f = open(test_script_fp, 'w')
test_f.write('''import sys
sys.path.insert(0, "../")
''')
for prot in processed_data.values():
    for domain in prot['domains']:
        name = domain['domain'].lower()
        with open(os.path.join(output_dir_fp, "%s.py" % name), 'w') as f:
            output = t.render(domain=domain)
            f.write(output)
            test_f.write('import chromewhip.protocol.%s\n' % name)

test_f.close()
