import os

from playwright.sync_api import Page, expect
import pytest
import requests

from cuke import Cuke
from cuke.errors import NoApiKey

URL = os.environ.get("CUKE_URL", "http://localhost:5000")
was_logged = False

@pytest.fixture
def clear_api_keys():
    try:
        os.remove(".cuke")
    except FileNotFoundError:
        pass
    if "CUKE_API_KEY" in os.environ:
        del os.environ["CUKE_API_KEY"]


def test_apikey(clear_api_keys):
    """Test api key none; read from kwargs; read from env vars; read from file
    Because it calls user_alias and the api key doesn't exist, it raises - but I did check and it's set correctly.
    """
    
    c = Cuke()
    assert c._api_key is None
    with pytest.raises(requests.exceptions.HTTPError):
        c = Cuke(api_key="asdf123", url=URL)
    os.environ["CUKE_API_KEY"] = "asdf123"
    with pytest.raises(requests.exceptions.HTTPError):
        c = Cuke(url=URL)
    del os.environ["CUKE_API_KEY"]
    c = Cuke(url=URL)
    with open(".cuke", "w") as f:
        f.write("asdf123")
    with pytest.raises(requests.exceptions.HTTPError):
        c = Cuke(url=URL)


def test_updates(clear_api_keys):
    c = Cuke(user_agent="python-client-test", url=URL)
    assert not len(c._dirty_set)
    c.hello = 123
    assert c._vars == {"hello": 123}
    assert "hello" in c._dirty_set
    assert c.hello == 123


def test_store_template(clear_api_keys):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "iz nice"
    resp = c._update()
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
    d._template = "iz not nice"
    d._update()
    page = requests.get(f"{URL}/page/python-client-test/{page_id}")
    assert "iz nice" not in page.text
    assert "iz not nice" in page.text
    with pytest.raises(NoApiKey):
        e = Cuke(user_agent="python-client-test", url=URL, page_slug=page_slug, page_id=page_id)

def test_store(clear_api_keys):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "iz nice {{ x }}"
    resp = c._update()
    url_segments = resp["url"].split("/")
    page_slug = url_segments[2]
    page_id = url_segments[3]
    c.x = "to meet you"
    c._update()
    d = Cuke(user_agent="python-client-test", url=URL, page_slug=page_slug, page_id=page_id, editor_key=resp["editor_key"])
    assert d._vars == {"x": "to meet you"}
    assert d._template == "iz nice {{ x }}"

def test_render(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", url=URL)
    # test 1 step update + set vars
    c._template = "hello {{ y }}"
    c.y = "inventor"
    resp = c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("hello inventor")
    # test 2 step update
    c._template = "iz nice {{ x }}"
    resp = c._update()
    c.x = "to play"
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice to play")
    c.x = "to meet you"
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice to meet you")

def test_code(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", url=URL)
    def setup():
        print("hello from python")
    c._setup = setup
    c._template = "iz nice"
    c._update()
    global was_logged  # playwright needs this as a global idk why
    was_logged = False
    def check_console(msg):
        if msg.text.startswith("Failed to load resource"):
            return True
        assert msg.text == "hello from python"
        global was_logged
        was_logged = True
    page.on("console", check_console)
    page.goto(f"{URL}/page/python-client-test/{c._page_id}", wait_until="networkidle")
    expect(page.locator("body")).to_contain_text("iz nice", timeout=10)
    assert was_logged

def test_private(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "iz nice"
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice")
    c._private = True
    c._update()
    resp = page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    assert resp.status == 404
    c._private = False
    c._update()
    resp = page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    assert resp.status == 200

def test_title(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "iz nice"
    c._title = "very nice"
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice")
    assert page.title() == "very nice - cuke.cool"
    c._title = "very very nice"
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    assert page.title() == "very very nice - cuke.cool"

def test_exec_websocket(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "iz nice {{ x }}"
    c.x = 'to be free'
    def setup():
        cuke.x = "to play"
        cuke._update()
    c.setup = setup
    update = c._update()
    assert update["setup"]["type"] == "function"
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice to be free")
    expect(page.locator("body")).not_to_contain_text("iz nice to play")
    resp = requests.get(f"{URL}/page/python-client-test/{c._page_id}/execute/setup", headers={"Authorization": c._editor_key})
    assert resp.status_code == 200
    import time; time.sleep(3)
    expect(page.locator("body")).to_contain_text("iz nice to play")

def test_button(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "{{ button('likes', 'increment') }} likes: {{ likes }}"
    c.likes = 0
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("likes: 0")
    import time; time.sleep(1)
    page.click("text=increment: likes")
    expect(page.locator("body")).to_contain_text("likes: 1")