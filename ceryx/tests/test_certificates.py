import os
import stat
import subprocess
import uuid

import redis
import requests

import client

ALL_CAN_READ = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH

CERTIFICATE_ROOT = "/usr/local/share/certificates"
CERYX_HOST = "ceryx"

redis_client = redis.Redis(host='redis')
testing_client = client.Client()


def test_custom_certificate():
    """
    Ensure that Ceryx uses the given certificate for each route, if configured
    so.
    """
    certificate_id = uuid.uuid4()
    certificate_path = f"{CERTIFICATE_ROOT}/{certificate_id}.crt"
    key_path = f"{CERTIFICATE_ROOT}/{certificate_id}.key"
    hostname = "custom-certificate.ceryx.test"

    command = [
        "openssl",
        "req", "-x509",
        "-newkey", "rsa:4096",
        "-keyout", key_path,
        "-out", certificate_path,
        "-days", "1",
        "-subj", f"/C=GR/ST=Attica/L=Athens/O=SourceLair/OU=Org/CN={hostname}",
        "-nodes",
    ]
    subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    os.chmod(certificate_path, ALL_CAN_READ)
    os.chmod(key_path, ALL_CAN_READ)

    api_base_url = "http://api:5555/"

    route_redis_key = f"ceryx:routes:{hostname}"
    redis_client.set(route_redis_key, api_base_url)

    settings_redis_key = f"ceryx:settings:{hostname}"
    redis_client.hset(settings_redis_key, "certificate_path", certificate_path)
    redis_client.hset(settings_redis_key, "key_path", key_path)

    testing_client.get(f"https://{hostname}/", verify=certificate_path)