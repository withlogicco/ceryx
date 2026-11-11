import os
import socket

from urllib3.connection import HTTPConnection, HTTPSConnection

DEFAULT_CERYX_HOST = "ceryx"  # Set by Docker Compose in tests
CERYX_HOST = os.getenv("CERYX_HOST", DEFAULT_CERYX_HOST)
CERYX_HOST_SUFFIXES = tuple(
    suffix.strip()
    for suffix in os.getenv("CERYX_TEST_HOST_SUFFIXES", ".ceryx.test").split(",")
    if suffix.strip()
)


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
        return self._dns_host.rstrip(".")

    @host.setter
    def host(self, value):
        """
        If the request header matches a configured Ceryx test suffix, force set the actual
        host to the configured Ceryx host, so as to send corresponding
        requests to Ceryx.
        """
        self._dns_host = CERYX_HOST if value.endswith(CERYX_HOST_SUFFIXES) else value


class CeryxTestsHTTPSConnection(CeryxTestsHTTPConnection, HTTPSConnection):
    def __init__(
        self,
        host,
        port=None,
        key_file=None,
        cert_file=None,
        key_password=None,
        strict=None,
        timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
        ssl_context=None,
        server_hostname=None,
        **kw,
    ):

        # urllib3 v2 removed the old ``strict`` argument. Keep accepting it for
        # compatibility with Requests/urllib3 call sites, but do not forward it.
        init_kwargs = dict(
            port=port,
            timeout=timeout,
            key_file=key_file,
            cert_file=cert_file,
            key_password=key_password,
            ssl_context=ssl_context,
            server_hostname=server_hostname,
        )
        init_kwargs.update(kw)

        while True:
            try:
                HTTPSConnection.__init__(self, host, **init_kwargs)
                break
            except TypeError as exc:
                message = str(exc)
                if "key_password" in message and "key_password" in init_kwargs:
                    init_kwargs.pop("key_password")
                    continue
                if "server_hostname" in message and "server_hostname" in init_kwargs:
                    init_kwargs.pop("server_hostname")
                    continue
                if "ssl_context" in message and "ssl_context" in init_kwargs:
                    init_kwargs.pop("ssl_context")
                    continue
                raise

        # ------------------------------
        # Original comment from upstream
        # ------------------------------
        #
        # Required property for Google AppEngine 1.9.0 which otherwise causes
        # HTTPS requests to go out as HTTP. (See Issue #356)
        self._protocol = "https"
