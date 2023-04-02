import pytest
import requests

from cuke import Cuke

URL = "http://localhost:5000"

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
    pass