from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

from .connection import CeryxTestsHTTPConnection, CeryxTestsHTTPSConnection


class CeryxTestsHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = CeryxTestsHTTPConnection

    def __init__(self, host, *args, **kwargs):
        """
        Store the original HTTP request host, so we can pass it over via the
        `Host` header.
        """
        self._impostor_host = host
        super().__init__(host, *args, **kwargs)
    
    def urlopen(self, *args, **kwargs):
        """
        This custom `urlopen` implementation enforces setting the `Host` header
        of the request to `self._impostor_host`.
        """
        kwargs["headers"]["Host"] = self._impostor_host
        return super().urlopen(*args, **kwargs)
 

class CeryxTestsHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = CeryxTestsHTTPSConnection

    def __init__(self, host, *args, **kwargs):
        """
        Force set SNI to the requested Host.
        """
        super().__init__(host, *args, **kwargs)
        self.conn_kw["server_hostname"] = host
