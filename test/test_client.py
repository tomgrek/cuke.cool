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

@pytest.fixture
def clear_funs():
    yield requests.get(f"{URL}/clear_funs")
    requests.get(f"{URL}/clear_funs")

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


def test_store_template_subslug(clear_api_keys):
    c = Cuke(user_agent="python-client-test", page_subslug="sluggy", url=URL)
    c._template = "iz nice"
    resp = c._update()
    url_segments = resp["url"].split("/")
    page_slug = url_segments[2]
    assert page_slug == "python-client-test"
    page_subslug = url_segments[-2]
    assert page_subslug == "sluggy"
    page_id = url_segments[-1]
    assert len(page_id) == 12
    assert len(resp["contributor_key"]) == 32
    assert len(resp["editor_key"]) == 32
    page = requests.get(f"{URL}/page/python-client-test/sluggy/{page_id}")
    assert "iz nice" in page.text
    d = Cuke(user_agent="python-client-test", url=URL, page_slug=page_slug, page_subslug="sluggy", page_id=page_id, editor_key=resp["editor_key"])
    d._template = "iz not nice"
    d._update()
    page = requests.get(f"{URL}/page/python-client-test/sluggy/{page_id}")
    assert "iz nice" not in page.text
    assert "iz not nice" in page.text
    with pytest.raises(NoApiKey):
        e = Cuke(user_agent="python-client-test", url=URL, page_slug=page_slug, page_subslug="sluggy", page_id=page_id)


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


def test_store_subslug(clear_api_keys):
    c = Cuke(user_agent="python-client-test", page_subslug="wiki", url=URL)
    c._template = "iz nice {{ x }}"
    resp = c._update()
    page_slug = resp["page_slug"]
    page_subslug = resp["page_subslug"]
    page_id = resp["page_id"]
    c.x = "to meet you"
    c._update()
    d = Cuke(user_agent="python-client-test", url=URL, page_slug=page_slug, page_subslug=page_subslug, page_id=page_id, editor_key=resp["editor_key"])
    assert d._vars == {"x": "to meet you"}
    assert d._template == "iz nice {{ x }}"


def test_render(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", url=URL)
    # test 1 step update + set vars
    c._template = "hello {{ y }}"
    c.y = "inventor"
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("hello inventor")
    # test 2 step update
    c._template = "iz nice {{ x }}"
    c._update()
    c.x = "to play"
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice to play")
    c.x = "to meet you"
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice to meet you")


def test_render_subslug(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", page_subslug="wiki", url=URL)
    # test 1 step update + set vars
    c._template = "hello {{ y }}"
    c.y = "inventor"
    resp = c._update()
    page.goto(f"{URL}/page/python-client-test/wiki/{c._page_id}")
    expect(page.locator("body")).to_contain_text("hello inventor")
    # test 2 step update
    c._template = "iz nice {{ x }}"
    resp = c._update()
    c.x = "to play"
    c._update()
    page.goto(f"{URL}/page/python-client-test/wiki/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice to play")
    c.x = "to meet you"
    c._update()
    page.goto(f"{URL}/page/python-client-test/wiki/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice to meet you")


def test_render_subslug_and_not_subslug(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", page_subslug="tomato", url=URL)
    c._template = "hello tomato"
    c._update()
    tomato_id = c._page_id
    c = Cuke(user_agent="python-client-test", page_subslug="tomatillo", url=URL)
    c._template = "hello tomatillo"
    c._update()
    page.goto(f"{URL}/page/python-client-test/tomato/{tomato_id}")
    expect(page.locator("body")).to_contain_text("hello tomato")
    page.goto(f"{URL}/page/python-client-test/tomatillo/{c._page_id}")
    expect(page.locator("body")).to_contain_text("hello tomatillo")


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


def test_code_subslug(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", page_subslug="biff", url=URL)
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
    page.goto(f"{URL}/page/python-client-test/biff/{c._page_id}", wait_until="networkidle")
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


def test_private_subslug(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", page_subslug="zebra", url=URL)
    c._template = "iz nice"
    c._update()
    page.goto(f"{URL}/page/python-client-test/zebra/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice")
    c._private = True
    c._update()
    resp = page.goto(f"{URL}/page/python-client-test/zebra/{c._page_id}")
    assert resp.status == 404
    c._private = False
    c._update()
    resp = page.goto(f"{URL}/page/python-client-test/zebra/{c._page_id}")
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


def test_title_subslug(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", page_subslug="seed", url=URL)
    c._template = "iz nice"
    c._title = "very nice"
    c._update()
    page.goto(f"{URL}/page/python-client-test/seed/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice")
    assert page.title() == "very nice - cuke.cool"
    c._title = "very very nice"
    c._update()
    page.goto(f"{URL}/page/python-client-test/seed/{c._page_id}")
    assert page.title() == "very very nice - cuke.cool"


def test_exec_websocket(clear_api_keys, page, clear_funs):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "iz nice {{ x }}"
    c.x = 'to be free'
    def setup(cuke):
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


def test_exec_websocket_subslug(clear_api_keys, page, clear_funs):
    c = Cuke(user_agent="python-client-test", page_subslug="foof", url=URL)
    c._template = "iz nice {{ x }}"
    c.x = 'to be free'
    def setup(cuke):
        cuke.x = "to play"
        cuke._update()
    c.setup = setup
    update = c._update()
    assert update["setup"]["type"] == "function"
    page.goto(f"{URL}/page/python-client-test/foof/{c._page_id}")
    expect(page.locator("body")).to_contain_text("iz nice to be free")
    expect(page.locator("body")).not_to_contain_text("iz nice to play")
    resp = requests.get(f"{URL}/page/python-client-test/foof/{c._page_id}/execute/setup", headers={"Authorization": c._editor_key})
    assert resp.status_code == 200
    import time; time.sleep(3)
    c = Cuke(page_subslug="foof", url=URL, editor_key=c._editor_key, page_id=c._page_id, page_slug=c._page_slug)
    assert c.x == "to play"
    expect(page.locator("body")).to_contain_text("iz nice to play")


def test_button(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "{{ button('likes', 'increment') }} {{ button('likes', 'decrement') }} likes: {{ likes }}"
    c.likes = 0
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("likes: 0")
    import time; time.sleep(1)
    page.click("text=increment: likes")
    expect(page.locator("body")).to_contain_text("likes: 1")
    page.click("text=decrement: likes")
    expect(page.locator("body")).to_contain_text("likes: 0")


def test_remote_execute(clear_api_keys):
    c = Cuke(user_agent="python-client-test", url=URL)
    c.x = "hello"
    c._template = ""
    def update(cuke):
        if cuke.x == "hello":
            cuke.x = "goodbye"
        else:
            cuke.x = "hello again"
        cuke._update()
    c.update = update
    c._update()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "hello"
    c.update()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "goodbye"
    c.update()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "hello again"


def test_remote_execute_subslug(clear_api_keys):
    c = Cuke(user_agent="python-client-test", url=URL, page_subslug="bobo")
    c.x = "hello"
    c._template = ""
    def update(cuke):
        if cuke.x == "hello":
            cuke.x = "goodbye"
        else:
            cuke.x = "hello again"
        cuke._update()
    c.update = update
    c._update()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_subslug=c._page_subslug, page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "hello"
    c.update()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_subslug=c._page_subslug, page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "goodbye"
    c.update()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_subslug=c._page_subslug, page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "hello again"


def test_no_apikey_when_editor(clear_api_keys):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "iz nice"
    c._update()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_id=c._page_id, editor_key=c._editor_key)
    assert c._api_key is None


def test_timed_execute(clear_api_keys, clear_funs):
    c = Cuke(user_agent="python-client-test", url=URL)
    c.x = "hello"
    c._template = ""
    def saybye(cuke):
        # cuke: every 12s
        cuke.x = "goodbye"
        cuke._update()
    c.saybye = saybye
    c._update()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "hello"
    import time; time.sleep(30)
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "goodbye"
    import time; time.sleep(20) # otherwise clear_funs might be invoked before /done is executed


def test_timed_execute_subslug(clear_api_keys, clear_funs):
    c = Cuke(user_agent="python-client-test", url=URL, page_subslug="minion")
    c.x = "hello"
    c._template = ""
    def saybye(cuke):
        # cuke: every 12s
        cuke.x = "goodbye"
        cuke._update()
    c.saybye = saybye
    c._update()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_subslug="minion", page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "hello"
    import time; time.sleep(30)
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_subslug="minion", page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "goodbye"
    import time; time.sleep(30) # otherwise clear_funs might be invoked before /done is executed


def test_knockon_execute(clear_api_keys, clear_funs):
    c = Cuke(user_agent="python-client-test", url=URL)
    c.x = "hello"
    c._template = ""
    def saybye(cuke):
        # cuke: every 10s
        cuke.x = "goodbye"
        cuke._update()
    def nawbro(cuke):
        # cuke: onchange x
        cuke.x = "nawbro"
        cuke._update()
    c.saybye = saybye
    c.nawbro = nawbro
    c._sync()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "hello"
    import time; time.sleep(30)
    c._sync()
    assert c.x == "nawbro"


def test_knockon_execute_subslug(clear_api_keys, clear_funs):
    c = Cuke(user_agent="python-client-test", url=URL, page_subslug="pinky")
    c.x = "hello"
    c._template = ""
    def saybye(cuke):
        # cuke: every 10s
        cuke.x = "goodbye"
        cuke._update()
    def nawbro(cuke):
        # cuke: onchange x
        cuke.x = "nawbro"
        cuke._update()
    c.saybye = saybye
    c.nawbro = nawbro
    c._sync()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_subslug="pinky", page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == "hello"
    import time; time.sleep(30)
    c._sync()
    assert c.x == "nawbro"


def test_knockon_execute_not_twice(clear_api_keys, clear_funs):
    c = Cuke(user_agent="python-client-test", url=URL)
    c.x = 1
    c._template = ""
    def addone(cuke):
        cuke.x += 1
        cuke._update()
    def onlyonceplease(cuke):
        # cuke: onchange x
        cuke.x += 1
        cuke._update()
    c.addone = addone
    c.onlyonceplease = onlyonceplease
    c._sync()
    c = Cuke(user_agent="python-client-test", url=URL, page_slug=c._page_slug, page_id=c._page_id, editor_key=c._editor_key)
    assert c.x == 1
    c.addone()
    import time; time.sleep(20)
    c._sync()
    assert c.x == 3


def test_simulated_subdomain(clear_api_keys):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "iz nice"
    resp = c._update()
    url_segments = resp["url"].split("/")
    page_slug = url_segments[2]
    assert page_slug == "python-client-test"
    page_id = url_segments[3]
    page = requests.get(f"{URL}/page/python-client-test/{page_id}")
    assert "iz nice" in page.text
    page = requests.get(f"{URL}/page/{page_id}", headers={"X-Subdomain-Fake": "python-client-test"})
    assert "iz nice" in page.text


def test_delete_page(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", page_id="fodder", api_key=os.environ["CUKE_FAKE_APIKEY"], url=URL)
    # test 1 step update + set vars
    c._template = "hello {{ y }}"
    c.y = "inventor"
    resp = c._update()
    page.goto(f"{URL}/page/{c._page_slug}/{c._page_id}")
    expect(page.locator("body")).to_contain_text("hello inventor")
    status = requests.delete(f"{URL}/user/delete_page/{c._page_id}")
    assert status.status_code == 401
    status = requests.delete(f"{URL}/user/delete_page/{c._page_id}", headers={"Authorization": os.environ["CUKE_FAKE_APIKEY"]})
    assert status.status_code == 200
    response = page.goto(f"{URL}/page/{c._page_slug}/{c._page_id}")
    assert response.status == 404


def test_loggedin(clear_api_keys, clear_funs):
    c = Cuke(user_agent="python-client-test", api_key=os.environ["CUKE_FAKE_APIKEY"], page_id="nomatter", url=URL)
    assert c._views == 0
    c._template = "hello"
    c._sync()
    assert c._views == 0
    requests.get(f"{URL}/page/testuser/nomatter")
    c._sync()
    assert c._views == 1


def test_math(clear_api_keys, page):
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "{{ button('likes', 'increment') }} {{ button('likes', 'decrement') }} likes: {{ likes }} mean: {{ math('likes', 'mean', 2) }} mean_of_all: {{ math('likes', 'mean', -1) }}"
    c.likes = 0
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("mean: 0")
    import time; time.sleep(1)
    page.click("text=increment: likes")
    expect(page.locator("body")).to_contain_text("mean: 0.5")
    page.click("text=increment: likes")
    expect(page.locator("body")).to_contain_text("mean: 1.5")
    expect(page.locator("body")).to_contain_text("mean_of_all: 1")
    c.likes = 5
    c._sync()
    import time; time.sleep(1)
    expect(page.locator("body")).to_contain_text("likes: 5")
    expect(page.locator("body")).to_contain_text("mean: 3.5")
    expect(page.locator("body")).to_contain_text("mean_of_all: 2.0")


def test_render_nobug(clear_api_keys, page):
    # There was a bug (unrelated to math) where not having a plain {{ likes }} would mess the rendering
    c = Cuke(user_agent="python-client-test", url=URL)
    c._template = "{{ button('likes', 'increment') }} {{ button('likes', 'decrement') }} mean: {{ math('likes', 'mean', 2) }} mean_of_all: {{ math('likes', 'mean', -1) }}"
    c.likes = 0
    c._update()
    page.goto(f"{URL}/page/python-client-test/{c._page_id}")
    expect(page.locator("body")).to_contain_text("mean: 0")
    import time; time.sleep(1)
    page.click("text=increment: likes")
    expect(page.locator("body")).to_contain_text("mean: 0.5")
    page.click("text=increment: likes")
    expect(page.locator("body")).to_contain_text("mean: 1.5")
    expect(page.locator("body")).to_contain_text("mean_of_all: 1")
    c.likes = 5
    c._sync()
    import time; time.sleep(1)
    expect(page.locator("body")).to_contain_text("mean: 3.5")
    expect(page.locator("body")).to_contain_text("mean_of_all: 2.0")