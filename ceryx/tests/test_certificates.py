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
        self.redis.set(self.redis_target_key, api_base_url)

        self.redis.hset(self.redis_settings_key, "certificate_path", certificate_path)
        self.redis.hset(self.redis_settings_key, "key_path", key_path)

        self.client.get(f"https://{self.host}/", verify=certificate_path)

    def test_fallback_certificate(self):
        """
        Ensure that Ceryx uses the fallback certificate if a route gets accessed
        via HTTPS with no configured certificate or automatic Let's Encrypt
        certificates enabled.
        """
        try:
            response = self.client.get(f"https://ghost.ceryx.test/", verify="/etc/ceryx/ssl/default.crt")
        except Exception as e:
            assert "sni-support-required-for-valid-ssl" in str(e)
