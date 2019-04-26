import os
import uuid

import redis

from client import CeryxTestClient


class BaseTest:
    def setup_method(self):
        self.uuid = uuid.uuid4()
        self.host = f"{self.uuid}.ceryx.test"
        self.redis_target_key = f"ceryx:routes:{self.host}"
        self.redis_settings_key = f"ceryx:settings:{self.host}"
        self.client = CeryxTestClient()
        self.redis = redis.Redis(host='redis')