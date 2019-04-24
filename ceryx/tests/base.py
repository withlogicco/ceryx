import os
import uuid

import redis

from client import CeryxTestClient


class BaseTest:
    def setup_method(self):
        self.uuid = uuid.uuid4()
        self.host = f"{self.uuid}.ceryx.test"
        self.client = CeryxTestClient()
        self.redis = redis.Redis(host='redis')