from cuke.errors import NoApiKey

def make_request_in_api_key_order(func, cls, url, json=None, allow_anonymous=False,
                                  anonymous_error_msg=""):

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
    if json is not None:
        resp = func(url, json=json, headers=headers)
    else:
        resp = func(url, headers=headers)
    return resp