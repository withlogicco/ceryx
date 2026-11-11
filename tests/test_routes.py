import time

import pytest
import requests
from client import CeryxTestClient
from utils import ceryx_api_base_url, ceryx_api_url


class TestRoutes:
    """Test suite for routing functionality"""

    @pytest.fixture
    def api_url(self):
        """Base API URL for routes"""
        return ceryx_api_url("/api/routes")

    @pytest.fixture
    def client(self):
        """HTTP client for making requests through Ceryx"""
        return CeryxTestClient()

    def test_no_route(self, backend, client):
        """
        Ceryx should send a `503` response when receiving a request with a `Host`
        header that has not been registered for routing.
        """
        response = client.get("http://i-do-not-exist.ceryx.test/")
        assert response.status_code == 503

    def test_proxy(self, backend, client, api_url, test_host):
        """
        Ceryx should successfully proxy the upstream request to the client, for a
        registered route.
        """
        # Register the local Ceryx API as a route
        target = ceryx_api_url("/api/routes/")
        route_data = {"source": test_host, "target": target}
        requests.post(api_url, json=route_data)

        upstream_response = client.get(target)
        ceryx_response = client.get(f"http://{test_host}/")

        assert upstream_response.status_code == ceryx_response.status_code
        assert upstream_response.json() == ceryx_response.json()

    def test_redirect(self, backend, client, api_url, test_host):
        """
        Ceryx should respond with 301 status and the appropriate `Location` header
        for redirected routes.
        """
        # Register the local Ceryx API as a redirect route
        target = ceryx_api_url("/api/routes")
        route_data = {
            "source": test_host,
            "target": target,
            "settings": {"mode": "redirect"},
        }
        requests.post(api_url, json=route_data)

        url = f"http://{test_host}/some/path/?some=args&more=args"
        target_url = f"{target}/some/path/?some=args&more=args"

        ceryx_response = client.get(url, allow_redirects=False)

        assert ceryx_response.status_code == 301
        assert ceryx_response.headers["Location"] == target_url

    def test_enforce_https(self, backend, client, api_url, test_host):
        """
        Ceryx should respond with 301 status and the appropriate `Location` header
        for routes with HTTPS enforced.
        """
        # Register route with HTTPS enforcement
        target = ceryx_api_url("/")
        route_data = {
            "source": test_host,
            "target": target,
            "settings": {"enforce_https": True},
        }
        requests.post(api_url, json=route_data)

        base_url = f"{test_host}/some/path/?some=args&more=args"
        http_url = f"http://{base_url}"
        https_url = f"https://{base_url}"
        ceryx_response = client.get(http_url, allow_redirects=False)

        assert ceryx_response.status_code == 301
        assert ceryx_response.headers["Location"] == https_url

    def test_wildcard_fallback(self, backend, client, api_url, mock_upstream):
        """
        Ceryx should use $wildcard route when no specific route matches
        """
        # Create wildcard route
        route_data = {"source": "$wildcard", "target": mock_upstream}
        requests.post(api_url, json=route_data)

        # Request to non-existent host should use wildcard
        response = client.get("http://non-existent-random-host.ceryx.test/")
        assert response.status_code == 200
        assert b"Mock upstream response" in response.content

    def test_wildcard_mode_fallback(self, backend, client, api_url):
        """Wildcard mode settings should apply when the host has no mode setting."""
        wildcard_target = ceryx_api_url("/api/routes")
        requests.post(
            api_url,
            json={
                "source": "$wildcard",
                "target": wildcard_target,
                "settings": {"mode": "redirect"},
            },
        )

        response = client.get(
            "http://wildcard-mode.ceryx.test/path?x=1",
            allow_redirects=False,
        )

        assert response.status_code == 301
        assert response.headers["Location"] == f"{wildcard_target}/path?x=1"

    def test_wildcard_enforce_https_fallback(
        self, backend, client, api_url, mock_upstream
    ):
        """Wildcard enforce_https should apply when the host has no host-specific setting."""
        requests.post(
            api_url,
            json={
                "source": "$wildcard",
                "target": mock_upstream,
                "settings": {"enforce_https": True},
            },
        )

        response = client.get(
            "http://wildcard-https.ceryx.test/path?y=1",
            allow_redirects=False,
        )

        assert response.status_code == 301
        assert (
            response.headers["Location"] == "https://wildcard-https.ceryx.test/path?y=1"
        )

    def test_route_enforce_https_false_overrides_wildcard(
        self, backend, client, api_url, test_host, mock_upstream
    ):
        """A route's own enforce_https: false wins over $wildcard's true."""
        requests.post(
            api_url,
            json={"source": "$wildcard", "target": mock_upstream, "settings": {"enforce_https": True}},
        )
        requests.post(
            api_url,
            json={"source": test_host, "target": mock_upstream, "settings": {"enforce_https": False}},
        )

        response = client.get(f"http://{test_host}/", allow_redirects=False)

        assert response.status_code == 200
        assert b"Mock upstream response" in response.content

    def test_route_proxy_mode_overrides_wildcard(
        self, backend, client, api_url, test_host, mock_upstream
    ):
        """A route's own mode: proxy wins over $wildcard's redirect."""
        requests.post(
            api_url,
            json={"source": "$wildcard", "target": mock_upstream, "settings": {"mode": "redirect"}},
        )
        requests.post(
            api_url,
            json={"source": test_host, "target": mock_upstream, "settings": {"mode": "proxy"}},
        )

        response = client.get(f"http://{test_host}/", allow_redirects=False)

        assert response.status_code == 200
        assert b"Mock upstream response" in response.content

    def test_specific_route_over_wildcard(
        self, backend, client, api_url, test_host, mock_upstream
    ):
        """
        Ceryx should prefer specific routes over wildcard fallback
        """
        # Create wildcard route
        wildcard_target = ceryx_api_url("/wildcard")
        route_data = {"source": "$wildcard", "target": wildcard_target}
        requests.post(api_url, json=route_data)

        # Create specific route
        route_data = {"source": test_host, "target": mock_upstream}
        requests.post(api_url, json=route_data)

        # Request to specific host should use specific route
        response = client.get(f"http://{test_host}/")
        assert response.status_code == 200
        assert b"Mock upstream response" in response.content

    def test_route_caching(self, backend, client, api_url, test_host, mock_upstream):
        """
        Ceryx should cache routes for 5 seconds
        """
        # Create route
        route_data = {"source": test_host, "target": mock_upstream}
        requests.post(api_url, json=route_data)

        # First request should work
        response = client.get(f"http://{test_host}/")
        assert response.status_code == 200
        # Delete route
        requests.delete(f"{api_url}/{test_host}")

        # Route deletion should invalidate cached lookups immediately.
        response = client.get(f"http://{test_host}/")
        assert response.status_code == 503

        # After 6 seconds, cache should expire and return 503
        time.sleep(6)
        response = client.get(f"http://{test_host}/")
        assert response.status_code == 503

    def test_path_preservation(
        self, backend, client, api_url, test_host, mock_upstream
    ):
        """
        Ceryx should preserve the request path when proxying
        """
        route_data = {"source": test_host, "target": mock_upstream}
        requests.post(api_url, json=route_data)

        # Request with path
        response = client.get(f"http://{test_host}/some/path/here")
        assert response.status_code == 200

    def test_query_string_preservation(
        self, backend, client, api_url, test_host, mock_upstream
    ):
        """
        Ceryx should preserve query strings when proxying
        """
        route_data = {"source": test_host, "target": mock_upstream}
        requests.post(api_url, json=route_data)

        # Request with query string
        response = client.get(f"http://{test_host}/path?param1=value1&param2=value2")
        assert response.status_code == 200

    def test_redirect_with_https_enforcement(self, backend, client, api_url, test_host):
        """
        Ceryx should handle both redirect mode and HTTPS enforcement
        """
        target = ceryx_api_base_url()
        route_data = {
            "source": test_host,
            "target": target,
            "settings": {"mode": "redirect", "enforce_https": True},
        }
        requests.post(api_url, json=route_data)

        # HTTP request should redirect to HTTPS
        http_url = f"http://{test_host}/test"
        response = client.get(http_url, allow_redirects=False)

        assert response.status_code == 301
        assert response.headers["Location"] == f"https://{test_host}/test"

    def test_multiple_routes_isolation(self, backend, client, api_url, mock_upstream):
        """
        Multiple routes should not interfere with each other
        """
        # Create multiple routes
        hosts = [f"test{i}.ceryx.test" for i in range(3)]
        for i, host in enumerate(hosts):
            route_data = {"source": host, "target": f"{mock_upstream}/{i}"}
            requests.post(api_url, json=route_data)

        # Each route should work independently
        for host in hosts:
            response = client.get(f"http://{host}/")
            assert response.status_code == 200

    def test_target_with_path(self, backend, client, api_url, test_host):
        """
        Ceryx should handle targets that include a path
        """
        target = ceryx_api_url("/api/routes")
        route_data = {"source": test_host, "target": target}
        requests.post(api_url, json=route_data)

        response = client.get(f"http://{test_host}/")
        assert response.status_code == 200
