import base64
import inspect
import io
import json
import os
import requests
import threading
import time
import weakref

from cuke.errors import NoApiKey, NoPageYet, SetPageIdOnInitialization
from cuke.util import make_request_in_api_key_order

KEYS_TO_NOT_UPDATE = {"_dirty_set", "_instant_updates", "_vars", "_vars_lock", "_daemon",
                      "_contributor_key", "_editor_key", "_page_id", "_page_slug", "_template"}

class Cuke:
    def __init__(self, url="https://cuke.cool", api_key=None, instant_updates=False,
                 page_slug=None, page_id=None, contributor_key=None, editor_key=None,
                 private=False, **kwargs):
        self._dirty_set = set()
        self._instant_updates = instant_updates
        self._vars = {}
        self._vars_lock = threading.Lock()
        self._daemon = None
        self._url = url
        self._api_key = api_key

        if self._api_key is None:
            self._api_key = os.environ.get("CUKE_API_KEY", None)
        if self._api_key is None:
            try:
                self._api_key = open(".cuke").read()
            except:
                pass
        
        self._user_agent = kwargs.get("user_agent", None)
        self._page_slug = page_slug or self._user_alias
        self._page_id = page_id
        self._contributor_key = contributor_key
        self._editor_key = editor_key
        
        self._webworker = None
        self._ui_thread_js_for_loop_output = None
        self._setup = None
        self._loop = None
        self._event = None
        self._frame_time = None
        self._packages = []
        self._template = None
        self._code = None

        self._private = private

        if self._page_id:
            self._initialize_vars()
        self._dirty_set = set()
    

    def __getattribute__(self, key):
        if not key.startswith("_"):
            return self._vars[key]
        return super().__getattribute__(key)
    

    def __setattr__(self, key, val):
        if not key.startswith("_"):
            with self._vars_lock:
                self._vars[key] = val
                self._dirty_set.add(key)
                if self._instant_updates:
                    self._update()
        else:
            super().__setattr__(key, val)
            if key not in KEYS_TO_NOT_UPDATE:
                self._dirty_set.add(key)
                if self._instant_updates:
                    self._update()

    @property
    def _user_alias(self):
        if self._api_key is None:
            return None
        resp = requests.get(f"{self._url}/user/get_alias", headers=self._headers(self._api_key))
        resp.raise_for_status()
        return resp.json()["alias"]

    def _initialize_vars(self):
        resp = make_request_in_api_key_order(requests.get, self, f"{self._url}/retrieve/{self._page_slug}/{self._page_id}",
                                             anonymous_error_msg="because you're trying to connect to an existing page, but without authentication.")
        if resp.status_code == 404:
            return False
        
        resp = resp.json()
        
        self._template = resp.pop("__template__")
        self._code = resp.pop("__code__")
        self._private = resp.pop("__private__")
        self._frame_time = self._code.get("frame_time")
        self._packages = self._code.get("packages")
        self._ui_thread_js_for_loop_output = self._code.get("ui_thread_js_for_loop_output")
        self._ui_thread_js_for_loop_input = self._code.get("ui_thread_js_for_loop_input")
        self._webworker = self._code.get("webworker")

        for k in resp:
            self._vars[k] = resp[k]["value"]
            # TODO may want to deserialize it back to a python obj, e.g. b64 string -> matplotlib figure
            # which obv is impossible, but, maybe it could be a message "this was originally a matplotlib figure,
            # we serialized it and now it's a PNG that looks like this"

    def _headers(self, key):
        return {"User-Agent": self._user_agent, "Authorization": key}


    def _update(self, initial=False):
        if not self._page_slug or not self._page_id:
            raise NoPageYet()
        if not len(self._dirty_set):
            return False
        update = {"__meta__": {}}
        for key in ("_private", ):
            if key in self._dirty_set:
                update["__meta__"][key] = getattr(self, key)
                self._dirty_set.remove(key)

        if initial:
            keys_to_update = self._vars
        else:
            keys_to_update = self._dirty_set
        for k in keys_to_update:
            try:
                json.dumps(self._vars[k])
                update[k] = {"type": "basic", "value": self._vars[k]}
            except Exception as e:
                if str(type(self._vars[k])) == "<class 'matplotlib.figure.Figure'>":
                    buf = io.BytesIO()
                    self._vars[k].savefig(buf, format="png")
                    update[k] = {"type": "png_b64", "value": base64.b64encode(buf.getvalue()).decode() }
                else:
                    update[k] = {"type": "error", "value": f"Could not serialize. {e}" }
        # TODO this needs error handling or it kills the thread
        resp = make_request_in_api_key_order(requests.post, self, f"{self._url}/store/{self._page_slug}/{self._page_id}", json=update)
        resp.raise_for_status()
        self._dirty_set = set()
        
        return False if not len(update) else update


    def _start(self, update_interval=1.5):
        """
        Start a background thread to send updates at an interval (specified in seconds).
        """
        assert not self._instant_updates, "You don't need a background thread if instant updates are on."
        def task(self_):
            while self_._run_thread and self_._main_thread.is_alive():
                if len(self._dirty_set):
                    with self_._vars_lock:
                        self_._update()
                time.sleep(update_interval)
        self._run_thread = True
        self._main_thread = threading.current_thread()
        self._daemon = threading.Thread(target=task, args=(weakref.proxy(self), ), daemon=True, name="updater")
        self._daemon.start()


    @property
    def _is_running(self):
        if self._daemon is None:
            return False
        return self._daemon.is_alive()


    def _stop(self):
        self._run_thread = False
        if self._daemon is not None:
            self._daemon.join()


    def __del__(self):
        self._stop()


    def _store_template(self, template, basic_auth={}):
        """
        Store a template. If basic_auth is provided - a dict with keys username and password - that will set the page up with
        HTTP basic auth.
        """
        if self._page_id is None and self._api_key is not None:
            raise SetPageIdOnInitialization()
        username = basic_auth.get("username", None)
        password = basic_auth.get("password", None)
        page_id = self._page_id or ""

        code = {}
        code["webworker"] = self._webworker
        code["ui_thread_js_for_loop_input"] = None
        # TODO i should probably add this. For example, in the setInterval call:
        # postMessage(`run_the_users_ui_input_code`) ... <user's code is run on ui thread; ui thread sends back a message>
        # onMessage(`from_ui_thread`, data => for key, val in data: pyodide.globals.set(key, val))
        # pyodide.runPython(`loop.bind(key1, key2, ...)()`)
        code["ui_thread_js_for_loop_output"] = self._ui_thread_js_for_loop_output
        code["frame_time"] = self._frame_time
        if self._setup:
            code["setup"] = inspect.getsource(self._setup).strip()
        if self._loop:
            code["loop"] = inspect.getsource(self._loop).strip()
        if self._event:
            code["event"] = inspect.getsource(self._event).strip()
        code["packages"] = self._packages
        
        resp = make_request_in_api_key_order(requests.post, self, f"{self._url}/store_template/{page_id}",
                                             json={"template": template, "username": username, 
                                             "password": password, "code": code}, allow_anonymous=True)

        resp.raise_for_status()

        self._template = template

        url = resp.json()["url"]
        if not self._api_key:
            _, _, self._page_slug, self._page_id = url.split("/")
        if not self._page_id:
            _, _, _, self._page_id = url.split("/")
        if not self._page_slug:
            _, _, self._page_slug, _ = url.split("/")
        self._contributor_key = resp.json()["contributor_key"]
        self._editor_key = resp.json()["editor_key"]
        
        return resp.json()