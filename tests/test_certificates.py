import pytest
import requests
from client import CeryxTestClient
from utils import (
    ceryx_api_url,
    create_certificates_for_host,
    pem_fingerprint,
    served_certificate_fingerprint,
)


def fingerprint(path):
    with open(path) as certificate:
        return pem_fingerprint(certificate.read())


@pytest.mark.parametrize("prefix", ["CERYX_TLS", "CERYX_SSL"])
def test_default_certificate_from_environment(backend, restart_ceryx, prefix):
    """CERYX_TLS_DEFAULT_*, or the CERYX_SSL_DEFAULT_* names from Ceryx 0.x."""
    certificate_path, key_path = create_certificates_for_host("default.ceryx.test")
    restart_ceryx(
        {
            f"{prefix}_DEFAULT_CERTIFICATE": certificate_path,
            f"{prefix}_DEFAULT_KEY": key_path,
        }
    )

    served = served_certificate_fingerprint("no-route.ceryx.test")
    assert served == fingerprint(certificate_path)


class TestCertificates:
    """Test suite for SSL certificate functionality."""

    @pytest.fixture
    def api_routes_url(self):
        return ceryx_api_url("/api/routes")

    @pytest.fixture
    def client(self):
        return CeryxTestClient()

    def test_custom_certificate(
        self, backend, client, api_routes_url, test_host, mock_upstream
    ):
        certificate_path, key_path = create_certificates_for_host(test_host)

        route_data = {
            "source": test_host,
            "target": mock_upstream,
            "settings": {
                "certificate_path": certificate_path,
                "key_path": key_path,
            },
        }
        response = requests.post(api_routes_url, json=route_data)
        assert response.status_code == 201

        response = client.get(f"https://{test_host}/", verify=certificate_path)
        assert response.status_code == 200

    def test_fallback_certificate(self, backend, client):
        with pytest.raises(requests.exceptions.SSLError):
            client.get(
                f"https://ghost.ceryx.test/", verify="/etc/ceryx/ssl/default.crt"
            )

    def test_wildcard_route_certificate_serves_hosts_without_a_route(
        self, backend, api_routes_url, mock_upstream
    ):
        wildcard_cert_path, wildcard_key_path = create_certificates_for_host(
            "wildcard.ceryx.test"
        )
        requests.post(
            api_routes_url,
            json={
                "source": "$wildcard",
                "target": mock_upstream,
                "settings": {
                    "certificate_path": wildcard_cert_path,
                    "key_path": wildcard_key_path,
                },
            },
        )
        try:
            served = served_certificate_fingerprint("no-route.ceryx.test")
            assert served == fingerprint(wildcard_cert_path)
        finally:
            requests.delete(f"{api_routes_url}/$wildcard")

    def test_routes_do_not_take_the_wildcard_route_certificate(
        self, backend, api_routes_url, test_host, mock_upstream
    ):
        """A route without certificate files gets the default certificate, not $wildcard's."""
        wildcard_cert_path, wildcard_key_path = create_certificates_for_host(
            "wildcard.ceryx.test"
        )
        requests.post(
            api_routes_url,
            json={
                "source": "$wildcard",
                "target": mock_upstream,
                "settings": {
                    "certificate_path": wildcard_cert_path,
                    "key_path": wildcard_key_path,
                },
            },
        )
        requests.post(api_routes_url, json={"source": test_host, "target": mock_upstream})
        try:
            served = served_certificate_fingerprint(test_host)
            assert served != fingerprint(wildcard_cert_path)
        finally:
            requests.delete(f"{api_routes_url}/$wildcard")

    def test_host_certificate_wins_over_wildcard_settings(
        self, backend, client, api_routes_url, test_host, mock_upstream
    ):
        wildcard_cert_path, wildcard_key_path = create_certificates_for_host(
            "wildcard.ceryx.test"
        )
        host_cert_path, host_key_path = create_certificates_for_host(test_host)

        requests.post(
            api_routes_url,
            json={
                "source": "$wildcard",
                "target": mock_upstream,
                "settings": {
                    "certificate_path": wildcard_cert_path,
                    "key_path": wildcard_key_path,
                },
            },
        )
        requests.post(
            api_routes_url,
            json={
                "source": test_host,
                "target": mock_upstream,
                "settings": {
                    "certificate_path": host_cert_path,
                    "key_path": host_key_path,
                },
            },
        )

        response = client.get(f"https://{test_host}/", verify=host_cert_path)
        assert response.status_code == 200
