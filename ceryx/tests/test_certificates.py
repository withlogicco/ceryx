from base import BaseTest
from utils import create_certificates_for_host


class TestCertificates(BaseTest):
    def test_custom_certificate(self):
        """
        Ensure that Ceryx uses the given certificate for each route, if configured
        so.
        """
        certificate_path , key_path = create_certificates_for_host(self.host)

        api_base_url = "http://api:5555/"

        route_redis_key = f"ceryx:routes:{self.host}"
        self.redis.set(route_redis_key, api_base_url)

        settings_redis_key = f"ceryx:settings:{self.host}"
        self.redis.hset(settings_redis_key, "certificate_path", certificate_path)
        self.redis.hset(settings_redis_key, "key_path", key_path)

        self.client.get(f"https://{self.host}/", verify=certificate_path)
