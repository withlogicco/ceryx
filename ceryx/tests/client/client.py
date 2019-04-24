from requests import Session

from .adapters import CeryxTestsHTTPAdapter


class CeryxTestClient(Session):
    def __init__(self):
        super().__init__()
        self.mount("http://", CeryxTestsHTTPAdapter())
        self.mount("https://", CeryxTestsHTTPAdapter())
