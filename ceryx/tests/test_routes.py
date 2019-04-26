from base import BaseTest


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
        # Register the local Ceryx API as a route
        target = f"http://api:5555/api/routes/"
        self.redis.set(self.redis_target_key, target)

        upstream_response = self.client.get(target)
        ceryx_response = self.client.get(f"http://{self.host}/")

        assert upstream_response.status_code == ceryx_response.status_code
        assert upstream_response.content == ceryx_response.content


    def test_redirect(self):
        """
        Ceryx should respond with 301 status and the appropriate `Location` header
        for redirected routes.
        """
        # Register the local Ceryx API as a redirect route
        target = "http://api:5555/api/routes"
        self.redis.set(self.redis_target_key, target)
        self.redis.hset(self.redis_settings_key, "mode", "redirect")

        url = f"http://{self.host}/some/path/?some=args&more=args"
        target_url = f"{target}/some/path/?some=args&more=args"

        ceryx_response = self.client.get(url, allow_redirects=False)
        
        assert ceryx_response.status_code == 301
        assert ceryx_response.headers["Location"] == target_url


    def test_enforce_https(self):
        """
        Ceryx should respond with 301 status and the appropriate `Location` header
        for routes with HTTPS enforced.
        """
        # Register the local Ceryx API as a redirect route
        target = "http://api:5555/"
        self.redis.set(self.redis_target_key, target)
        self.redis.hset(self.redis_settings_key, "enforce_https", "1")

        base_url = f"{self.host}/some/path/?some=args&more=args"
        http_url = f"http://{base_url}"
        https_url = f"https://{base_url}"
        ceryx_response = self.client.get(http_url, allow_redirects=False)

        assert ceryx_response.status_code == 301
        assert ceryx_response.headers["Location"] == https_url
