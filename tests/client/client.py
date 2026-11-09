from requests import Session

from .adapters import CeryxTestsHTTPAdapter


class CeryxTestClient(Session):
    """
    The Ceryx testing client lets us test Ceryx hosts without any
    configuration. Essentially lets us make requests to
    hostnames ending in `.ceryx.test`, without any name resolution
    needed. The testing client will make these requests to the configured
    Ceryx host automatically, but will set both the `Host` HTTP header
    and `SNI` SSL attribute to the initial host.
    """

    def __init__(self):
        super().__init__()
        self.mount("http://", CeryxTestsHTTPAdapter())
        self.mount("https://", CeryxTestsHTTPAdapter())
