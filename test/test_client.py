import os

import pytest
import requests

from cuke import Cuke

URL = os.environ.get("CUKE_URL", "http://localhost:5000")

def test_apikey():
    """Test api key none; read from kwargs; read from env vars; read from file
    Because it calls user_alias and the api key doesn't exist, it raises - but I did check and it's set correctly.
    """
    try:
        os.remove(".cuke")
    except FileNotFoundError:
        pass
    c = Cuke()
    assert c._api_key is None
    with pytest.raises(requests.exceptions.HTTPError):
        c = Cuke(api_key="asdf123")
    os.environ["CUKE_API_KEY"] = "asdf123"
    with pytest.raises(requests.exceptions.HTTPError):
        c = Cuke()
    del os.environ["CUKE_API_KEY"]
    c = Cuke()
    with open(".cuke", "w") as f:
        f.write("asdf123")
    with pytest.raises(requests.exceptions.HTTPError):
        c = Cuke()


def test_updates():
    c = Cuke(user_agent="python-client-test", url=URL)
    assert not len(c._dirty_set)
    c.hello = 123
    assert c._vars == {"hello": 123}
    assert "hello" in c._dirty_set
    assert c.hello == 123


def test_store_template():
    c = Cuke(user_agent="python-client-test", url=URL)
    resp = c._store_template("iz nice")
    url_segments = resp["url"].split("/")
    page_slug = url_segments[2]
    assert page_slug == "python-client-test"
    page_id = url_segments[3]
    assert len(page_id) == 12
    assert len(resp["contributor_key"]) == 32
    assert len(resp["editor_key"]) == 32
    page = requests.get(f"{URL}/page/python-client-test/{page_id}")
    assert "iz nice" in page.text
    d = Cuke(user_agent="python-client-test", url=URL, page_slug=page_slug, page_id=page_id, editor_key=resp["editor_key"])
    d._store_template("iz not nice")
    page = requests.get(f"{URL}/page/python-client-test/{page_id}")
    assert "iz nice" not in page.text
    assert "iz not nice" in page.text
    e = Cuke(user_agent="python-client-test", url=URL, page_slug=page_slug, page_id=page_id)
    with pytest.raises(requests.exceptions.HTTPError):
        e._store_template("iz not nice")

def test_store():
    c = Cuke(user_agent="python-client-test", url=URL)
    resp = c._store_template("iz nice {{ x }}")
    url_segments = resp["url"].split("/")
    page_slug = url_segments[2]
    page_id = url_segments[3]
    c.x = "to meet you"
    c._update()
    d = Cuke(user_agent="python-client-test", url=URL, page_slug=page_slug, page_id=page_id, editor_key=resp["editor_key"])
    assert d._vars == {"x": "to meet you"}
