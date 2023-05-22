class Image:
    def __init__(self, path=None, data=None):
        if path is None and data is None:
            raise ValueError("Either path or data must be provided")
        self.path = path
        self._data = data
    @property
    def data(self):
        if self._data is None:
            with open(self.path, "rb") as f:
                self._data = f.read()
        return self._data