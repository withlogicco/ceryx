from requests.adapters import DEFAULT_POOLBLOCK, HTTPAdapter

from .poolmanager import CeryxTestsPoolManager


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