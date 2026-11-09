from urllib3.poolmanager import PoolManager

from .connectionpool import (
    CeryxTestsHTTPConnectionPool,
    CeryxTestsHTTPSConnectionPool,
)


class CeryxTestsPoolManager(PoolManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pool_classes_by_scheme = {
            "http": CeryxTestsHTTPConnectionPool,
            "https": CeryxTestsHTTPSConnectionPool,
        }