from urllib3.connection import HTTPConnection, HTTPSConnection
import os
import socket


DEFAULT_CERYX_HOST = "ceryx"  # Set by Docker Compose in tests
CERYX_HOST = os.getenv("CERYX_HOST", DEFAULT_CERYX_HOST)


class CeryxTestsHTTPConnection(HTTPConnection):
    """
    Custom-built HTTPConnection for Ceryx tests. Force sets the request's
    host to the configured Ceryx host, if the request's original host
    ends with `.ceryx.test`.
    """
    
    @property
    def host(self):
        """
        Do what the original property did. We just want to touch the setter.
        """
        return self._dns_host.rstrip('.')
    
    @host.setter
    def host(self, value):
        """
        If the request header ends with `.ceryx.test` then force set the actual
        host to the configured Ceryx host, so as to send corresponding
        requests to Ceryx.
        """
        self._dns_host = CERYX_HOST if value.endswith(".ceryx.test") else value


class CeryxTestsHTTPSConnection(CeryxTestsHTTPConnection, HTTPSConnection):
    def __init__(
        self, host, port=None, key_file=None, cert_file=None,
        key_password=None, strict=None,
        timeout=socket._GLOBAL_DEFAULT_TIMEOUT, ssl_context=None,
        server_hostname=None, **kw,
    ):

        # Initialise the HTTPConnection subclass created above.
        CeryxTestsHTTPConnection.__init__(
            self, host, port, strict=strict, timeout=timeout, **kw,
        )

        self.key_file = key_file
        self.cert_file = cert_file
        self.key_password = key_password
        self.ssl_context = ssl_context
        self.server_hostname = server_hostname

        # ------------------------------
        # Original comment from upstream
        # ------------------------------
        #
        # Required property for Google AppEngine 1.9.0 which otherwise causes
        # HTTPS requests to go out as HTTP. (See Issue #356)
        self._protocol = 'https'
 