import os
import socket

from requests import Session
from requests.adapters import DEFAULT_POOLBLOCK, HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.poolmanager import PoolManager


DEFAULT_CERYX_HOST = "ceryx"  # Set by Docker Compose in tests
CERYX_HOST = os.getenv("CERYX_HOST", DEFAULT_CERYX_HOST)


class CeryxTestsHTTPConnection(HTTPConnection):
    """
    Custom-built HTTPConnection for Ceryx tests. 
    """
    
    @property
    def host(self):
        return self._dns_host.rstrip('.')
    
    @host.setter
    def host(self, value):
        """
        Do exactly what the parent class does.
        """
        self._dns_host = CERYX_HOST if value.endswith(".ceryx.test") else value


class CeryxTestsHTTPSConnection(CeryxTestsHTTPConnection, HTTPSConnection):
    def __init__(
        self, host, port=None, key_file=None, cert_file=None,
        key_password=None, strict=None,
        timeout=socket._GLOBAL_DEFAULT_TIMEOUT, ssl_context=None,
        server_hostname=None, **kw,
    ):

        CeryxTestsHTTPConnection.__init__(
            self, host, port, strict=strict, timeout=timeout, **kw,
        )

        self.key_file = key_file
        self.cert_file = cert_file
        self.key_password = key_password
        self.ssl_context = ssl_context
        self.server_hostname = server_hostname

        # Required property for Google AppEngine 1.9.0 which otherwise causes
        # HTTPS requests to go out as HTTP. (See Issue #356)
        self._protocol = 'https'
 

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


class CeryxTestsPoolManager(PoolManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool_classes_by_scheme = {
            "http": CeryxTestsHTTPConnectionPool,
            "https": CeryxTestsHTTPSConnectionPool,
        }


class CeryxTestsHTTPAdapter(HTTPAdapter):
    def init_poolmanager(
        self, connections, maxsize, block=DEFAULT_POOLBLOCK, **pool_kwargs,
    ):
        # Comment from original Requests HTTPAdapter: Save these values for pickling
        self._pool_connections = connections
        self._pool_maxsize = maxsize
        self._pool_block = block

        self.poolmanager = CeryxTestsPoolManager(
            num_pools=connections, maxsize=maxsize, block=block, strict=True,
            **pool_kwargs,
        )


class Client(Session):
    def __init__(self):
        super().__init__()
        self.mount("http://", CeryxTestsHTTPAdapter())
        self.mount("https://", CeryxTestsHTTPAdapter())
