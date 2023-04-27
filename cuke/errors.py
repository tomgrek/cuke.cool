class NoApiKey(Exception):
    """No api key set"""
    def __init__(self, msg):
        super().__init__(f"No API key set, and it's required ({msg}). Generate one at https://cuke.cool/user/dashboard.")

class NoPageYet(Exception):
    """Either anonymous and no page_id yet, or api_key specified but not initialized with an id.
    Make a page first."""
    def __init__(self):
        super().__init__("Make a page first! (set cuke._template)")

class SetPageIdOnInitialization(Exception):
    """Didn't set page id"""
    def __init__(self):
        super().__init__("You have an API key, so you need to set a page id when you first intantiate Cuke()")