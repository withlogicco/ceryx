"""Ceryx keeps Let's Encrypt state in its storage backend.

These tests store Let's Encrypt state where resty.auto-ssl keeps it and read it
back through a Ceryx with Let's Encrypt enabled, without a certificate
authority. Against a Redis that requires a password (the test stack's
redis-password profile), they also check that Let's Encrypt storage
authenticates with CERYX_REDIS_PASSWORD.
"""

import sqlite3
import uuid

import requests
from utils import SQLITE_TEST_DB


def store_lets_encrypt_value(backend, redis_client, key, value):
    """Store a value where resty.auto-ssl's storage adapter for backend reads it."""
    if backend == "redis":
        redis_client.set(key, value)
        return

    with sqlite3.connect(SQLITE_TEST_DB) as db:
        db.execute(
            "INSERT INTO resource (kind, key, value) VALUES ('cert_data', ?, ?)",
            (key, value),
        )


def test_acme_challenge_is_served_from_storage(
    backend, lets_encrypt_host, redis_client, test_host
):
    token = uuid.uuid4().hex
    key_authorization = f"{token}.account-thumbprint"
    store_lets_encrypt_value(
        backend, redis_client, f"{test_host}:challenge:{token}", key_authorization
    )

    response = requests.get(
        f"http://{lets_encrypt_host}/.well-known/acme-challenge/{token}",
        headers={"Host": test_host},
        timeout=10,
    )

    assert response.status_code == 200
    assert response.text.strip() == key_authorization
