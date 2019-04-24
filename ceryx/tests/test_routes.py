import os

import requests

from base import BaseTest


CERYX_API_URL = os.getenv("CERYX_API_URL", "http://api:5555")
CERYX_API_ROUTES_ROOT = os.path.join(CERYX_API_URL, "api/routes")

CERYX_HOST = "http://ceryx"


class TestRoutes(BaseTest):
    def test_no_route(self):
        """
        Ceryx should send a `503` response when receiving a request with a `Host`
        header that has not been registered for routing.
        """
        response = self.client.get("http://i-do-not-exist.ceryx.test/")
        assert response.status_code == 503


    def test_proxy(self):
        """
        Ceryx should successfully proxy the upstream request to the client, for a
        registered route.
        """
        api_upstream_host = "api"
        ceryx_route_source = "api.ceryx.test"
        ceryx_route_target = f"http://{api_upstream_host}:5555/api/routes"

        # Register the local Ceryx API as a route
        register_api_response = requests.post(
            CERYX_API_ROUTES_ROOT,
            json={"source": ceryx_route_source, "target": ceryx_route_target},
        )

        upstream_response = self.client.get(ceryx_route_target)
        ceryx_response = self.client.get(f"http://{ceryx_route_source}/")

        assert upstream_response.status_code == ceryx_response.status_code
        assert upstream_response.content == ceryx_response.content


    def test_redirect(self):
        """
        Ceryx should respond with 301 status and the appropriate `Location` header
        for redirected routes.
        """
        api_upstream_host = "api"
        ceryx_route_target = "http://api:5555/api/routes"
        ceryx_route_source = "redirected-api.ceryx.test"

        # Register the local Ceryx API as a route
        register_api_response = requests.post(
            CERYX_API_ROUTES_ROOT,
            json={
                "source": ceryx_route_source,
                "target": ceryx_route_target,
                "settings": {"mode": "redirect"},
            },
        )

        url = f"http://{ceryx_route_source}/some/path/?some=args&more=args"
        target_url = f"{ceryx_route_target}/some/path/?some=args&more=args"

        ceryx_response = self.client.get(url, allow_redirects=False)
        
        assert ceryx_response.status_code == 301
        assert ceryx_response.headers["Location"] == target_url


    def test_enforce_https(self):
        """
        Ceryx should respond with 301 status and the appropriate `Location` header
        for routes with HTTPS enforced.
        """
        api_upstream_host = "api"
        api_upstream_target = "http://api:5555/"
        ceryx_route_source = "secure-api.ceryx.test"

        # Register the local Ceryx API as a route
        register_api_response = requests.post(
            CERYX_API_ROUTES_ROOT,
            json={
                "source": ceryx_route_source,
                "target": api_upstream_target,
                "settings": {"enforce_https": True},
            },
        )

        base_url = f"{ceryx_route_source}/some/path/?some=args&more=args"
        http_url = f"http://{base_url}"
        https_url = f"https://{base_url}"
        ceryx_response = self.client.get(http_url, allow_redirects=False)

        assert ceryx_response.status_code == 301
        assert ceryx_response.headers["Location"] == https_url
