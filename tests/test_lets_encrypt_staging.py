import os
import time

import pytest
import requests
from client import CeryxTestClient
from utils import LE_STAGING_CA, ceryx_api_url


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.lets_encrypt,
    pytest.mark.skipif(
        not os.environ.get("CERYX_LE_STAGING_DOMAIN"),
        reason="Run CERYX_LE_STAGING_DOMAIN=<public domain pointing at this Ceryx> pytest -m lets_encrypt.",
    ),
]


@pytest.fixture
def public_domain():
    return os.environ["CERYX_LE_STAGING_DOMAIN"]


@pytest.fixture
def api_url():
    return ceryx_api_url("/api/routes")


def test_lets_encrypt_staging_issues_and_serves_certificate(
    backend, api_url, public_domain, mock_upstream
):
    assert os.environ.get("CERYX_DISABLE_LETS_ENCRYPT", "").lower() != "true"
    assert os.environ.get("CERYX_LETS_ENCRYPT_CA") == LE_STAGING_CA

    response = requests.post(
        api_url,
        json={"source": public_domain, "target": mock_upstream},
        timeout=5,
    )
    assert response.status_code in {200, 201}

    client = CeryxTestClient()
    deadline = time.time() + int(os.environ.get("CERYX_LE_STAGING_TIMEOUT", "180"))
    last_error = None

    while time.time() < deadline:
        try:
            response = client.get(f"https://{public_domain}/", verify=False, timeout=10)
            if (
                response.status_code == 200
                and b"Mock upstream response" in response.content
            ):
                return
            last_error = AssertionError(
                f"Unexpected response: {response.status_code} {response.text[:200]}"
            )
        except Exception as exc:  # noqa: BLE001 - keep retrying while ACME issuance is in progress
            last_error = exc
        time.sleep(5)

    raise AssertionError(
        f"Let's Encrypt staging certificate was not served in time: {last_error}"
    )
