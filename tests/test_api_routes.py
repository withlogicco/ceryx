import json
import os
import sqlite3

import pytest
import requests
from client import CeryxTestClient
from utils import SQLITE_TEST_DB, ceryx_api_url



def get_routes_by_source(routes):
    return {route["source"]: route for route in routes}


def get_sqlite_route_record(host):
    if not os.path.exists(SQLITE_TEST_DB):
        return None

    with sqlite3.connect(SQLITE_TEST_DB) as db:
        row = db.execute(
            "SELECT value, meta FROM resource WHERE kind = ? AND key = ?",
            ("route", host),
        ).fetchone()

    if row is None:
        return None

    value, meta_json = row
    return value, json.loads(meta_json or "{}")


class TestAPIRoutes:
    """Test suite for /api/routes/ endpoints."""

    @pytest.fixture
    def api_url(self):
        return ceryx_api_url("/api/routes")

    def assert_non_wildcard_storage(self, backend, redis_client, host, target):
        if backend == "redis":
            assert redis_client.get(f"ceryx:routes:{host}") is None
            settings = redis_client.hgetall(f"ceryx:settings:{host}")
            assert settings[b"target"] == target.encode()
            return

        record = get_sqlite_route_record(host)
        assert record is not None
        value, meta = record
        assert value == ""
        assert meta["target"] == target

    def assert_wildcard_storage(self, backend, redis_client, target):
        if backend == "redis":
            assert redis_client.get("ceryx:routes:$wildcard") == target.encode()
            assert redis_client.hget("ceryx:settings:$wildcard", "target") is None
            return

        record = get_sqlite_route_record("$wildcard")
        assert record is not None
        value, meta = record
        assert value == target
        assert "target" not in meta

    def test_default_settings_are_stored(self, backend, api_url, redis_client, test_host):
        """enforce_https and mode are stored even at their defaults."""
        response = requests.post(api_url, json={"source": test_host, "target": "http://app:8000"})
        assert response.status_code == 201

        if backend == "redis":
            settings = redis_client.hgetall(f"ceryx:settings:{test_host}")
            assert settings[b"enforce_https"] == b"false"
            assert settings[b"mode"] == b"proxy"
            return

        _, meta = get_sqlite_route_record(test_host)
        assert meta["enforce_https"] is False
        assert meta["mode"] == "proxy"

    def test_list_routes_empty(self, backend, api_url):
        response = requests.get(api_url)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_route(
        self, backend, api_url, test_host, mock_upstream, redis_client
    ):
        response = requests.post(
            api_url, json={"source": test_host, "target": mock_upstream}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source"] == test_host
        assert data["target"] == mock_upstream

        response = requests.get(api_url)
        data = get_routes_by_source(response.json())
        assert data[test_host]["target"] == mock_upstream

        self.assert_non_wildcard_storage(
            backend, redis_client, test_host, mock_upstream
        )

    def test_create_route_with_settings(
        self, backend, api_url, test_host, mock_upstream
    ):
        route_data = {
            "source": test_host,
            "target": mock_upstream,
            "settings": {"enforce_https": True, "mode": "redirect"},
        }

        response = requests.post(api_url, json=route_data)
        assert response.status_code == 201

        response = requests.get(f"{api_url}/{test_host}")
        data = response.json()
        assert data["target"] == mock_upstream
        assert data["settings"]["enforce_https"] is True
        assert data["settings"]["mode"] == "redirect"

    def test_create_route_missing_source(self, backend, api_url, mock_upstream):
        response = requests.post(api_url, json={"target": mock_upstream})
        assert response.status_code == 400

    def test_create_route_missing_target(self, backend, api_url, test_host):
        response = requests.post(api_url, json={"source": test_host})
        assert response.status_code == 400

    def test_create_route_invalid_json(self, backend, api_url):
        response = requests.post(
            api_url,
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400

    def test_get_route(self, backend, api_url, test_host, mock_upstream):
        requests.post(api_url, json={"source": test_host, "target": mock_upstream})

        response = requests.get(f"{api_url}/{test_host}")
        assert response.status_code == 200
        assert response.json()["target"] == mock_upstream

    def test_get_route_not_found(self, backend, api_url):
        response = requests.get(f"{api_url}/nonexistent.ceryx.test")
        assert response.status_code == 404

    def test_update_route(
        self, backend, api_url, test_host, mock_upstream, redis_client
    ):
        requests.post(api_url, json={"source": test_host, "target": mock_upstream})

        new_target = "http://new-upstream:9999"
        response = requests.put(f"{api_url}/{test_host}", json={"target": new_target})
        assert response.status_code == 200

        response = requests.get(f"{api_url}/{test_host}")
        data = response.json()
        assert data["target"] == new_target

        self.assert_non_wildcard_storage(backend, redis_client, test_host, new_target)

    def test_update_route_settings(self, backend, api_url, test_host, mock_upstream):
        requests.post(api_url, json={"source": test_host, "target": mock_upstream})

        response = requests.put(
            f"{api_url}/{test_host}",
            json={"target": mock_upstream, "settings": {"enforce_https": True}},
        )
        assert response.status_code == 200

        response = requests.get(f"{api_url}/{test_host}")
        data = response.json()
        assert data["settings"]["enforce_https"] is True

    def test_update_route_not_found(self, backend, api_url):
        response = requests.put(
            f"{api_url}/nonexistent.ceryx.test",
            json={"target": "http://example.com"},
        )
        assert response.status_code == 404

    def test_update_route_mismatched_source(
        self, backend, api_url, test_host, mock_upstream
    ):
        requests.post(api_url, json={"source": test_host, "target": mock_upstream})

        response = requests.put(
            f"{api_url}/{test_host}",
            json={"source": "other.ceryx.test", "target": "http://example.com"},
        )
        assert response.status_code == 400

        response = requests.get(f"{api_url}/{test_host}")
        assert response.json()["target"] == mock_upstream

    def test_delete_route(self, backend, api_url, test_host, mock_upstream):
        requests.post(api_url, json={"source": test_host, "target": mock_upstream})

        response = requests.delete(f"{api_url}/{test_host}")
        assert response.status_code == 204

        response = requests.get(f"{api_url}/{test_host}")
        assert response.status_code == 404

    def test_delete_route_not_found(self, backend, api_url):
        response = requests.delete(f"{api_url}/nonexistent.ceryx.test")
        assert response.status_code == 204

    def test_list_multiple_routes(self, backend, api_url, mock_upstream):
        hosts = [f"test{i}.ceryx.test" for i in range(3)]
        for host in hosts:
            requests.post(
                api_url, json={"source": host, "target": f"{mock_upstream}/{host}"}
            )

        response = requests.get(api_url)
        assert response.status_code == 200
        data = response.json()

        sources = {route["source"] for route in data}
        for host in hosts:
            assert host in sources

    def test_route_proxy_works(self, backend, api_url, test_host, mock_upstream):
        requests.post(api_url, json={"source": test_host, "target": mock_upstream})

        client = CeryxTestClient()
        response = client.get(f"http://{test_host}")
        assert response.status_code == 200
        assert b"Mock upstream response" in response.content

    def test_route_mutations_apply_without_reload(
        self, backend, api_url, test_host, mock_upstream
    ):
        client = CeryxTestClient()

        create_response = requests.post(
            api_url, json={"source": test_host, "target": mock_upstream}
        )
        assert create_response.status_code == 201

        response = client.get(f"http://{test_host}/")
        assert response.status_code == 200
        assert b"Mock upstream response" in response.content

        updated_target = ceryx_api_url("/api/routes")
        update_response = requests.put(
            f"{api_url}/{test_host}", json={"target": updated_target}
        )
        assert update_response.status_code == 200

        response = client.get(f"http://{test_host}/")
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("application/json")

        delete_response = requests.delete(f"{api_url}/{test_host}")
        assert delete_response.status_code == 204

        response = client.get(f"http://{test_host}/")
        assert response.status_code == 503

    def test_wildcard_route(self, backend, api_url, mock_upstream, redis_client):
        response = requests.post(
            api_url, json={"source": "$wildcard", "target": mock_upstream}
        )
        assert response.status_code == 201

        response = requests.get(f"{api_url}/$wildcard")
        assert response.status_code == 200
        assert response.json()["target"] == mock_upstream

        self.assert_wildcard_storage(backend, redis_client, mock_upstream)

    def test_list_routes_ignores_stale_redis_settings(
        self, backend, api_url, redis_client
    ):
        if backend != "redis":
            pytest.skip("Redis-specific migration behavior")

        redis_client.hset("ceryx:settings:stale.ceryx.test", "mode", "redirect")

        response = requests.get(api_url)
        data = get_routes_by_source(response.json())
        assert "stale.ceryx.test" not in data

    def test_get_route_reads_legacy_redis_route_key(
        self, backend, api_url, redis_client
    ):
        if backend != "redis":
            pytest.skip("Redis-specific migration behavior")

        host = "legacy.ceryx.test"
        target = "http://legacy-upstream:8080"
        redis_client.set(f"ceryx:routes:{host}", target)

        response = requests.get(f"{api_url}/{host}")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == host
        assert data["target"] == target
