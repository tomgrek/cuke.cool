import inspect
from itertools import dropwhile

from cuke.errors import NoApiKey

def make_request_in_api_key_order(func, cls, url, json=None, allow_anonymous=False,
                                  anonymous_error_msg="", additional_headers=None):

    if cls._api_key is not None:
        headers = cls._headers(cls._api_key)
    elif cls._editor_key is not None:
        headers = cls._headers(cls._editor_key)
    elif cls._contributor_key is not None:
        headers = cls._headers(cls._contributor_key)
    else:
        if allow_anonymous is False:
            raise NoApiKey(anonymous_error_msg)
        else:
            headers = cls._headers(None)
    if additional_headers is not None:
        headers.update(additional_headers)
    if json is not None:
        resp = func(url, json=json, headers=headers)
    else:
        resp = func(url, headers=headers)
    return resp


def get_function_body(func):
    source_lines = inspect.getsourcelines(func)[0]
    source_lines = dropwhile(lambda x: x.startswith('@'), source_lines)
    line = next(source_lines).strip()
    if not line.startswith('def '):
        return line.rsplit(':')[-1].strip()
    elif not line.endswith(':'):
        for line in source_lines:
            line = line.strip()
            if line.endswith(':'):
                break
    first_line = next(source_lines)
    indentation = len(first_line) - len(first_line.lstrip())
    return ''.join([first_line[indentation:]] + [line[indentation:] for line in source_lines])


def add_header_to_function(body, name):
    lines = ["    " + line for line in body.split('\n')]
    func = f"def {name}(cuke):\n" + "\n".join(lines)
    exec(func)
    return locals()[name]
