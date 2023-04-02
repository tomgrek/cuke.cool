import json
import os
import requests
import threading
import time
import weakref

from cuke.errors import NoApiKey, NoPageYet, SetPageIdOnInitialization

class Cuke:
    def __init__(self, url="https://cuke.cool", api_key=None, instant_updates=False,
                 page_slug=None, page_id=None, contributor_key=None, editor_key=None,
                 **kwargs):
        self._vars = {}
        self._vars_lock = threading.Lock()
        self._daemon = None
        self._url = url
        self._api_key = api_key
        self._instant_updates = instant_updates

        if self._api_key is None:
            self._api_key = os.environ.get("CUKE_API_KEY", None)
        if self._api_key is None:
            try:
                self._api_key = open(".cuke").read()
            except:
                pass
        
        self._dirty_set = set()
        self._page_slug = page_slug or self._user_alias
        self._page_id = page_id
        self._contributor_key = contributor_key
        self._editor_key = editor_key
        self._user_agent = kwargs.get("user_agent", None)
        if self._page_id:
            self._initialize_vars()
    

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


    @property
    def _user_alias(self):
        if self._api_key is None:
            return None
        resp = requests.get(f"{self._url}/user/get_alias", headers=self._headers(self._api_key))
        resp.raise_for_status()
        return resp.json()["alias"]

    def _initialize_vars(self):
        if self._api_key is not None:
            resp = requests.get(f"{self._url}/retrieve/{self._page_slug}/{self._page_id}", headers=self._headers(self._api_key))
        elif self._editor_key is not None:
            resp = requests.get(f"{self._url}/retrieve/{self._page_slug}/{self._page_id}", headers=self._headers(self._editor_key))
        elif self._contributor_key is not None:
            resp = requests.get(f"{self._url}/retrieve/{self._page_slug}/{self._page_id}", headers=self._headers(self._contributor_key))
        else:
            raise NoApiKey()
        self._vars = resp.json()

    def _headers(self, key):
        return {"User-Agent": self._user_agent, "Authorization": key}


    def _update(self, initial=False):
        if not self._page_slug or not self._page_id:
            raise NoPageYet()
        if not len(self._dirty_set):
            return False
        update = {}
        if initial:
            keys_to_update = self._vars
        else:
            keys_to_update = self._dirty_set
        for k in keys_to_update:
            try:
                json.dumps(self._vars[k])
                update[k] = self._vars[k]
            except Exception as e:
                update[k] = f"Could not serialize. {e}"
        # TODO this needs error handling or it kills the thread
        if self._api_key is not None:
            resp = requests.post(f"{self._url}/store/{self._page_slug}/{self._page_id}", json=update, headers=self._headers(self._api_key))
        elif self._editor_key is not None:
            resp = requests.post(f"{self._url}/store/{self._page_slug}/{self._page_id}", json=update, headers=self._headers(self._editor_key))
        elif self._contributor_key is not None:
            resp = requests.post(f"{self._url}/store/{self._page_slug}/{self._page_id}", json=update, headers=self._headers(self._contributor_key))
        else:
            raise NoApiKey()
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
        
        if self._api_key is not None:
            resp = requests.post(f"{self._url}/store_template/{page_id}", json={"template": template, "username": username, "password": password}, headers=self._headers(self._api_key))
        elif self._editor_key is not None:
            resp = requests.post(f"{self._url}/store_template/{page_id}", json={"template": template, "username": username, "password": password}, headers=self._headers(self._editor_key))
        elif self._contributor_key is not None:
            resp = requests.post(f"{self._url}/store_template/{page_id}", json={"template": template, "username": username, "password": password}, headers=self._headers(self._contributor_key))
        else:
            resp = requests.post(f"{self._url}/store_template/{page_id}", json={"template": template, "username": username, "password": password}, headers=self._headers(self._api_key))        

        resp.raise_for_status()
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