from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

from .connection import CeryxTestsHTTPConnection, CeryxTestsHTTPSConnection


class CeryxTestsHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = CeryxTestsHTTPConnection

    def __init__(self, host, *args, **kwargs):
        self._impostor_host = host
        super().__init__(host, *args, **kwargs)
    
    def urlopen(self, *args, **kwargs):
        kwargs["headers"]["Host"] = self._impostor_host
        return super().urlopen(*args, **kwargs)
 

class CeryxTestsHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = CeryxTestsHTTPSConnection

    def __init__(self, host, *args, **kwargs):
        super().__init__(host, *args, **kwargs)
        self.conn_kw["server_hostname"] = host
