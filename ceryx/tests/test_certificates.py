import os
import stat
import subprocess
import uuid

import redis
import requests

from client import CeryxTestClient
from utils import create_certificates_for_host


CERYX_HOST = "ceryx"

redis_client = redis.Redis(host='redis')
test_client = CeryxTestClient()


def test_custom_certificate():
    """
    Ensure that Ceryx uses the given certificate for each route, if configured
    so.
    """
    host = f"{uuid.uuid4()}.ceryx.test"
    certificate_path , key_path = create_certificates_for_host(host)

    api_base_url = "http://api:5555/"

    route_redis_key = f"ceryx:routes:{host}"
    redis_client.set(route_redis_key, api_base_url)

    settings_redis_key = f"ceryx:settings:{host}"
    redis_client.hset(settings_redis_key, "certificate_path", certificate_path)
    redis_client.hset(settings_redis_key, "key_path", key_path)

    test_client.get(f"https://{host}/", verify=certificate_path)
