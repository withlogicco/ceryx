import pytest
import requests
from client import CeryxTestClient
from utils import (
    ceryx_api_url,
    create_certificates_for_host,
    pem_fingerprint,
    served_certificate_fingerprint,
)


def create_certificate_payload(domain):
    cert_path, key_path = create_certificates_for_host(domain.replace("*", "wildcard"))

    with open(cert_path, "r") as f:
        cert_pem = f.read()

    with open(key_path, "r") as f:
        key_pem = f.read()

    return {
        "domain": domain,
        "certificate": cert_pem,
        "private_key": key_pem,
    }


class TestAPICertificates:
    """Test suite for /api/certificates/ endpoints."""

    @pytest.fixture
    def api_url(self):
        return ceryx_api_url("/api/certificates")

    def test_list_certificates_empty(self, backend, api_url):
        response = requests.get(api_url)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_certificate(self, backend, api_url, test_host):
        response = requests.post(api_url, json=create_certificate_payload(test_host))
        assert response.status_code == 201

        response = requests.get(api_url)
        assert response.status_code == 200
        assert any(item["domain"] == test_host for item in response.json())

    def test_create_certificate_missing_domain(self, backend, api_url, test_host):
        payload = create_certificate_payload(test_host)
        cert_data = {
            "certificate": payload["certificate"],
            "private_key": payload["private_key"],
        }
        response = requests.post(api_url, json=cert_data)
        assert response.status_code == 400

    def test_create_certificate_missing_certificate(self, backend, api_url, test_host):
        cert_data = {"domain": test_host}
        response = requests.post(api_url, json=cert_data)
        assert response.status_code == 400

    def test_create_certificate_invalid_json(self, backend, api_url):
        response = requests.post(
            api_url, data="invalid json", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400

    def test_get_certificate(self, backend, api_url, test_host):
        requests.post(api_url, json=create_certificate_payload(test_host))
        response = requests.get(f"{api_url}/{test_host}")
        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == test_host
        assert data["has_certificate"] is True

    def test_get_certificate_not_found(self, backend, api_url):
        response = requests.get(f"{api_url}/nonexistent.ceryx.test")
        assert response.status_code == 404

    def test_delete_certificate(self, backend, api_url, test_host):
        requests.post(api_url, json=create_certificate_payload(test_host))
        response = requests.delete(f"{api_url}/{test_host}")
        assert response.status_code == 204

        response = requests.get(f"{api_url}/{test_host}")
        assert response.status_code == 404

    def test_delete_certificate_not_found(self, backend, api_url):
        response = requests.delete(f"{api_url}/nonexistent.ceryx.test")
        assert response.status_code == 204

    def test_list_multiple_certificates(self, backend, api_url):
        domains = [f"test{i}.ceryx.test" for i in range(3)]
        for domain in domains:
            requests.post(api_url, json=create_certificate_payload(domain))

        response = requests.get(api_url)
        assert response.status_code == 200
        data = response.json()
        found_domains = {item["domain"] for item in data}
        for domain in domains:
            assert domain in found_domains

    def test_wildcard_certificate(self, backend, api_url):
        wildcard_domain = "*.ceryx.test"

        response = requests.post(
            api_url, json=create_certificate_payload(wildcard_domain)
        )
        assert response.status_code == 201

        response = requests.get(f"{api_url}/{wildcard_domain}")
        assert response.status_code == 200

    def test_update_certificate(self, backend, api_url, test_host):
        requests.post(api_url, json=create_certificate_payload(test_host))

        update_data = create_certificate_payload(test_host)
        response = requests.post(api_url, json=update_data)
        assert response.status_code == 201

        response = requests.get(f"{api_url}/{test_host}")
        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == test_host
        assert data["has_certificate"] is True

    def test_certificate_with_special_characters(self, backend, api_url):
        domains = ["*.example.ceryx.test", "sub.*.ceryx.test"]

        for domain in domains:
            response = requests.post(api_url, json=create_certificate_payload(domain))
            assert response.status_code == 201

            response = requests.get(f"{api_url}/{domain}")
            assert response.status_code == 200

    def test_certificate_mutations_apply_without_reload(
        self, backend, api_url, test_host
    ):
        client = CeryxTestClient()
        payload = create_certificate_payload(test_host)

        create_response = requests.post(api_url, json=payload)
        assert create_response.status_code == 201

        response = client.get(f"https://{test_host}/", verify=False)
        assert response.status_code in {200, 503}

        update_response = requests.post(
            api_url, json=create_certificate_payload(test_host)
        )
        assert update_response.status_code == 201

        response = requests.get(f"{api_url}/{test_host}")
        assert response.status_code == 200
        assert response.json()["has_certificate"] is True

        delete_response = requests.delete(f"{api_url}/{test_host}")
        assert delete_response.status_code == 204

        response = requests.get(f"{api_url}/{test_host}")
        assert response.status_code == 404


class TestAPICertificateUpdate:
    """PUT /api/certificates/{domain} updates an existing certificate."""

    @pytest.fixture
    def api_url(self):
        return ceryx_api_url("/api/certificates")

    def test_put_missing_certificate_returns_404(self, backend, api_url, test_host):
        response = requests.put(
            f"{api_url}/{test_host}", json=create_certificate_payload(test_host)
        )
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_put_does_not_update_through_wildcard(self, backend, api_url):
        requests.post(api_url, json=create_certificate_payload("*.put.ceryx.test"))

        response = requests.put(
            f"{api_url}/host.put.ceryx.test",
            json=create_certificate_payload("host.put.ceryx.test"),
        )
        assert response.status_code == 404

    def test_put_replaces_certificate(self, backend, api_url, test_host):
        requests.post(api_url, json=create_certificate_payload(test_host))

        payload = create_certificate_payload(test_host)
        response = requests.put(f"{api_url}/{test_host}", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["domain"] == test_host
        assert data["has_certificate"] is True
        assert data["has_chain"] is False

    def test_put_without_domain_uses_url(self, backend, api_url, test_host):
        requests.post(api_url, json=create_certificate_payload(test_host))

        payload = create_certificate_payload(test_host)
        del payload["domain"]
        response = requests.put(f"{api_url}/{test_host}", json=payload)
        assert response.status_code == 200
        assert response.json()["domain"] == test_host

    def test_put_mismatched_domain_returns_400(self, backend, api_url, test_host):
        requests.post(api_url, json=create_certificate_payload(test_host))

        payload = create_certificate_payload(test_host)
        payload["domain"] = "other.ceryx.test"
        response = requests.put(f"{api_url}/{test_host}", json=payload)
        assert response.status_code == 400

        response = requests.get(api_url)
        assert "other.ceryx.test" not in {item["domain"] for item in response.json()}

    def test_put_certificate_without_key_returns_400(self, backend, api_url, test_host):
        requests.post(api_url, json=create_certificate_payload(test_host))

        payload = create_certificate_payload(test_host)
        response = requests.put(
            f"{api_url}/{test_host}", json={"certificate": payload["certificate"]}
        )
        assert response.status_code == 400

    def test_put_meta_only_keeps_material(self, backend, api_url, test_host):
        original = create_certificate_payload(test_host)
        original["chain"] = original["certificate"]
        requests.post(api_url, json=original)

        response = requests.put(
            f"{api_url}/{test_host}", json={"meta": {"vendor": "manual"}}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_chain"] is True
        assert data["meta"]["vendor"] == "manual"

        assert served_certificate_fingerprint(test_host) == pem_fingerprint(
            original["certificate"]
        )

    def test_put_new_certificate_without_chain_clears_chain(
        self, backend, api_url, test_host
    ):
        original = create_certificate_payload(test_host)
        original["chain"] = original["certificate"]
        requests.post(api_url, json=original)

        response = requests.put(
            f"{api_url}/{test_host}", json=create_certificate_payload(test_host)
        )
        assert response.status_code == 200
        assert response.json()["has_chain"] is False

        response = requests.get(f"{api_url}/{test_host}")
        assert response.json()["has_chain"] is False

    def test_put_applies_to_tls_without_reload(self, backend, api_url, test_host):
        original = create_certificate_payload(test_host)
        requests.post(api_url, json=original)
        assert served_certificate_fingerprint(test_host) == pem_fingerprint(
            original["certificate"]
        )

        replacement = create_certificate_payload(test_host)
        assert pem_fingerprint(replacement["certificate"]) != pem_fingerprint(
            original["certificate"]
        )
        response = requests.put(f"{api_url}/{test_host}", json=replacement)
        assert response.status_code == 200

        assert served_certificate_fingerprint(test_host) == pem_fingerprint(
            replacement["certificate"]
        )
