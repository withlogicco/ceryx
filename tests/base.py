import os
import uuid

import redis
from client import CeryxTestClient


def redis_test_client():
    host = os.environ.get("CERYX_REDIS_HOST", "redis")
    try:
        return redis.Redis(host=host, protocol=2)
    except TypeError:
        return redis.Redis(host=host)


class BaseTest:
    def setup_method(self):
        self.uuid = uuid.uuid4()
        self.host = f"{self.uuid}.ceryx.test"
        self.redis_target_key = f"ceryx:routes:{self.host}"
        self.redis_settings_key = f"ceryx:settings:{self.host}"
        self.client = CeryxTestClient()
        self.redis = redis_test_client()
