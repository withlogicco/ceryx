"""Client certificates (mTLS), per route.

A route requires client certificates with its own mtls_* settings. Routes are
created with CERYX_ROUTE_SETTINGS_DEFAULT_* for the settings they don't pass,
and a route without a CA or depth of its own uses CERYX_MTLS_DEFAULT_* at
request time. Clients without a certificate signed by the route's CA get 403.
"""

import os
import shutil
import socket
import ssl
import subprocess
from pathlib import Path

import pytest
import requests
from client import CeryxTestClient
from utils import ceryx_api_url

ROUTES_URL = ceryx_api_url("/api/routes")
CERYX_HOST = os.environ.get("CERYX_HOST", "ceryx")


def openssl(*arguments):
    subprocess.run(
        ["openssl", *arguments],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@pytest.fixture(scope="session")
def mtls_material():
    """A client CA, a client certificate it signed, and an unrelated self-signed one.

    Lives where Ceryx can read it too: the test stack shares this directory.
    """
    base = Path("/usr/local/share/certificates/ceryx-mtls-test")
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(mode=0o755, parents=True)

    ca_key, ca_cert = base / "ca.key", base / "ca.crt"
    client_key, client_csr, client_cert = base / "client.key", base / "client.csr", base / "client.crt"
    other_key, other_cert = base / "other.key", base / "other.crt"

    openssl("req", "-x509", "-newkey", "rsa:2048", "-days", "1", "-nodes",
            "-subj", "/CN=Ceryx Test Client CA", "-keyout", ca_key, "-out", ca_cert)
    openssl("req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=valid-client",
            "-keyout", client_key, "-out", client_csr)
    openssl("x509", "-req", "-days", "1", "-in", client_csr, "-CA", ca_cert,
            "-CAkey", ca_key, "-CAcreateserial", "-out", client_cert)
    # Self-signed, so it is also the CA of another route in some tests.
    openssl("req", "-x509", "-newkey", "rsa:2048", "-days", "1", "-nodes",
            "-subj", "/CN=Ceryx Test Other CA", "-keyout", other_key, "-out", other_cert)

    for path in (ca_cert, client_cert, client_key, other_cert, other_key):
        os.chmod(path, 0o644)

    return {
        "ca": str(ca_cert),
        "client": (str(client_cert), str(client_key)),
        "other": (str(other_cert), str(other_key)),
    }


def mtls(ca, **settings):
    return {
        "enforce_https": True,
        "mtls_require_client_certificate": True,
        "mtls_trusted_ca": ca,
        **settings,
    }


def create_route(host, settings=None, expected=201):
    response = requests.post(
        ROUTES_URL,
        json={"source": host, "target": ceryx_api_url("/api/routes"), "settings": settings or {}},
        timeout=10,
    )
    assert response.status_code == expected, response.text
    return response.json()


def update_route(host, settings, expected=200):
    response = requests.put(f"{ROUTES_URL}/{host}", json={"settings": settings}, timeout=10)
    assert response.status_code == expected, response.text
    return response.json()


def https_status(host, cert=None):
    return CeryxTestClient().get(f"https://{host}/", verify=False, cert=cert, timeout=10).status_code


def status_with_sni(sni, host, cert=None):
    """Status of a request for host over a TLS connection opened for sni."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    if cert:
        context.load_cert_chain(*cert)
    with socket.create_connection((CERYX_HOST, 443), timeout=10) as raw:
        with context.wrap_socket(raw, server_hostname=sni) as connection:
            connection.sendall(f"GET / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
            response = b""
            while chunk := connection.recv(65536):
                response += chunk
    return int(response.split(b" ", 2)[1])


def requested_client_ca_names(host):
    """CA names Ceryx sends when it asks for a client certificate for host, or None."""
    result = subprocess.run(
        ["openssl", "s_client", "-connect", f"{CERYX_HOST}:443", "-servername", host],
        input="",
        capture_output=True,
        text=True,
        timeout=10,
    )
    marker = "Acceptable client certificate CA names"
    if marker not in result.stdout:
        return None
    return result.stdout.split(marker, 1)[1].split("\n---", 1)[0]


@pytest.fixture
def wildcard_cleanup():
    yield
    # Through the API, so Ceryx also drops its cached $wildcard settings.
    requests.delete(f"{ROUTES_URL}/$wildcard", timeout=10)


def test_route_without_mtls_needs_no_client_certificate(backend, test_host):
    create_route(test_host)

    assert https_status(test_host) == 200


def test_mtls_route_rejects_missing_client_certificate(backend, test_host, mtls_material):
    create_route(test_host, mtls(mtls_material["ca"]))

    assert https_status(test_host) == 403


def test_mtls_route_rejects_untrusted_client_certificate(backend, test_host, mtls_material):
    create_route(test_host, mtls(mtls_material["ca"]))

    assert https_status(test_host, cert=mtls_material["other"]) == 403


def test_mtls_route_accepts_trusted_client_certificate(backend, test_host, mtls_material):
    create_route(test_host, mtls(mtls_material["ca"]))

    assert https_status(test_host, cert=mtls_material["client"]) == 200


def test_mtls_over_http2(backend, test_host, mtls_material):
    from test_http2 import request

    create_route(test_host, mtls(mtls_material["ca"]))

    assert request(test_host)[:2] == ("2", 403)
    assert request(test_host, client_cert=mtls_material["client"])[:2] == ("2", 200)


def test_mtls_settings_round_trip(backend, test_host, mtls_material):
    created = create_route(test_host, mtls(mtls_material["ca"], mtls_verify_depth=2))

    expected = {
        "mtls_require_client_certificate": True,
        "mtls_trusted_ca": mtls_material["ca"],
        "mtls_verify_depth": 2,
    }
    assert {key: created["settings"][key] for key in expected} == expected
    assert "client_auth" not in created

    fetched = requests.get(f"{ROUTES_URL}/{test_host}", timeout=10).json()
    assert fetched == created


def test_mtls_is_off_when_not_set(backend, test_host):
    settings = create_route(test_host)["settings"]

    assert settings["mtls_require_client_certificate"] is False
    assert settings["mtls_trusted_ca"] is None
    assert settings["mtls_verify_depth"] is None


def test_mtls_requires_enforce_https(backend, test_host, mtls_material):
    response = create_route(test_host, mtls(mtls_material["ca"], enforce_https=False), expected=400)
    assert "enforce_https" in response["detail"]

    create_route(test_host)
    response = update_route(
        test_host,
        {"mtls_require_client_certificate": True, "mtls_trusted_ca": mtls_material["ca"]},
        expected=400,
    )
    assert "enforce_https" in response["detail"]


def test_mtls_requires_a_trusted_ca(backend, test_host):
    response = create_route(
        test_host,
        {"enforce_https": True, "mtls_require_client_certificate": True},
        expected=400,
    )
    assert "mtls_trusted_ca" in response["detail"]


def test_mtls_trusted_ca_must_be_readable(backend, test_host):
    response = create_route(test_host, mtls("/does/not/exist/client-ca.pem"), expected=400)
    assert "mtls_trusted_ca" in response["detail"]


@pytest.mark.parametrize("depth", [-1, "two", 1.5])
def test_mtls_verify_depth_must_be_a_non_negative_integer(backend, test_host, mtls_material, depth):
    response = create_route(test_host, mtls(mtls_material["ca"], mtls_verify_depth=depth), expected=400)
    assert "mtls_verify_depth" in response["detail"]


def test_mtls_require_client_certificate_must_be_a_boolean(backend, test_host, mtls_material):
    response = create_route(
        test_host, mtls(mtls_material["ca"], mtls_require_client_certificate="maybe"), expected=400
    )
    assert "mtls_require_client_certificate" in response["detail"]


def test_mtls_changes_apply_without_reload(backend, test_host, mtls_material):
    create_route(test_host, {"enforce_https": True})
    assert https_status(test_host) == 200

    update_route(test_host, {"mtls_require_client_certificate": True, "mtls_trusted_ca": mtls_material["ca"]})
    assert https_status(test_host) == 403
    assert https_status(test_host, cert=mtls_material["client"]) == 200

    update_route(test_host, {"mtls_require_client_certificate": False})
    assert https_status(test_host) == 200


def test_mtls_is_per_route(backend, mtls_material):
    protected, public = "mtls-protected.ceryx.test", "mtls-public.ceryx.test"
    create_route(protected, mtls(mtls_material["ca"]))
    create_route(public)

    assert https_status(protected) == 403
    assert https_status(public) == 200


def test_host_header_cannot_bypass_mtls(backend, mtls_material):
    protected, public = "mtls-protected.ceryx.test", "mtls-public.ceryx.test"
    create_route(protected, mtls(mtls_material["ca"]))
    create_route(public)

    # The TLS connection is for the public route, so Ceryx asked for no client
    # certificate; the request itself is for the protected one. 421 makes
    # clients that reuse connections across hostnames (HTTP/2) retry on a
    # connection for the protected route, where they are asked for one.
    assert status_with_sni(public, protected) == 421


def test_client_certificate_for_another_route_is_rejected(backend, mtls_material):
    first, second = "mtls-first.ceryx.test", "mtls-second.ceryx.test"
    create_route(first, mtls(mtls_material["other"][0]))
    create_route(second, mtls(mtls_material["ca"]))

    assert status_with_sni(first, first, cert=mtls_material["other"]) == 200
    # Valid for the first route's CA, sent on the first route's connection.
    assert status_with_sni(first, second, cert=mtls_material["other"]) == 421
    # On the second route's own connection, it isn't trusted.
    assert status_with_sni(second, second, cert=mtls_material["other"]) == 403


def test_handshake_asks_for_client_certificates_only_on_mtls_routes(backend, mtls_material):
    protected, public = "mtls-protected.ceryx.test", "mtls-public.ceryx.test"
    create_route(protected, mtls(mtls_material["ca"]))
    create_route(public)

    names = requested_client_ca_names(protected)
    assert names is not None and "Ceryx Test Client CA" in names
    assert requested_client_ca_names(public) is None


def test_wildcard_route_mtls_applies_to_hosts_without_a_route(
    backend, test_host, mtls_material, wildcard_cleanup
):
    create_route("$wildcard", mtls(mtls_material["ca"]))

    assert https_status(test_host) == 403
    assert https_status(test_host, cert=mtls_material["client"]) == 200


def test_routes_do_not_take_the_wildcard_route_mtls(
    backend, test_host, mtls_material, wildcard_cleanup
):
    create_route("$wildcard", mtls(mtls_material["ca"]))
    create_route(test_host)

    assert https_status(test_host) == 200


def test_client_auth_api_is_gone(backend):
    response = requests.get(ceryx_api_url("/api/client-auth"), timeout=10)
    assert response.status_code == 404


# Defaults from the environment. These restart the tests' own Ceryx, so they
# skip with the Compose test stack.

def route_defaults(mtls_material):
    """New routes require HTTPS and client certificates from the default CA."""
    return {
        "CERYX_ROUTE_SETTINGS_DEFAULT_ENFORCE_HTTPS": "true",
        "CERYX_ROUTE_SETTINGS_DEFAULT_MTLS_REQUIRE_CLIENT_CERTIFICATE": "true",
        "CERYX_MTLS_DEFAULT_TRUSTED_CA": mtls_material["ca"],
    }


def test_route_settings_defaults_are_stored_on_new_routes(
    backend, restart_ceryx, test_host, mtls_material
):
    restart_ceryx(route_defaults(mtls_material))
    settings = create_route(test_host)["settings"]

    assert settings["enforce_https"] is True
    assert settings["mtls_require_client_certificate"] is True
    assert settings["mtls_trusted_ca"] is None
    assert https_status(test_host) == 403
    assert https_status(test_host, cert=mtls_material["client"]) == 200
    response = CeryxTestClient().get(f"http://{test_host}/", allow_redirects=False, timeout=10)
    assert response.status_code == 301


def test_routes_can_opt_out_of_the_route_settings_defaults(
    backend, restart_ceryx, test_host, mtls_material
):
    restart_ceryx(route_defaults(mtls_material))
    settings = create_route(test_host, {"mtls_require_client_certificate": False})["settings"]

    assert settings["mtls_require_client_certificate"] is False
    assert https_status(test_host) == 200


def test_route_settings_defaults_do_not_change_existing_routes(
    backend, restart_ceryx, test_host, mtls_material
):
    create_route(test_host)
    restart_ceryx(route_defaults(mtls_material))

    settings = requests.get(f"{ROUTES_URL}/{test_host}", timeout=10).json()["settings"]
    assert settings["mtls_require_client_certificate"] is False
    assert https_status(test_host) == 200


def test_new_routes_cannot_drop_https_while_requiring_mtls(
    backend, restart_ceryx, test_host, mtls_material
):
    restart_ceryx(route_defaults(mtls_material))

    response = create_route(test_host, {"enforce_https": False}, expected=400)
    assert "enforce_https" in response["detail"]


def test_default_trusted_ca_serves_routes_without_their_own(
    backend, restart_ceryx, test_host, mtls_material
):
    restart_ceryx({"CERYX_MTLS_DEFAULT_TRUSTED_CA": mtls_material["ca"]})
    settings = create_route(
        test_host, {"enforce_https": True, "mtls_require_client_certificate": True}
    )["settings"]

    assert settings["mtls_trusted_ca"] is None
    assert https_status(test_host) == 403
    assert https_status(test_host, cert=mtls_material["client"]) == 200
    names = requested_client_ca_names(test_host)
    assert names is not None and "Ceryx Test Client CA" in names


def test_changing_the_default_trusted_ca_applies_to_existing_routes(
    backend, restart_ceryx, test_host, mtls_material
):
    restart_ceryx({"CERYX_MTLS_DEFAULT_TRUSTED_CA": mtls_material["ca"]})
    create_route(test_host, {"enforce_https": True, "mtls_require_client_certificate": True})

    restart_ceryx({"CERYX_MTLS_DEFAULT_TRUSTED_CA": mtls_material["other"][0]})

    assert https_status(test_host, cert=mtls_material["client"]) == 403
    assert https_status(test_host, cert=mtls_material["other"]) == 200


def test_route_trusted_ca_wins_over_the_default(
    backend, restart_ceryx, test_host, mtls_material
):
    restart_ceryx({"CERYX_MTLS_DEFAULT_TRUSTED_CA": mtls_material["other"][0]})
    create_route(test_host, mtls(mtls_material["ca"]))

    assert https_status(test_host, cert=mtls_material["client"]) == 200
    assert https_status(test_host, cert=mtls_material["other"]) == 403


def test_routes_relying_on_a_removed_default_ca_answer_500(
    backend, restart_ceryx, test_host, mtls_material
):
    restart_ceryx({"CERYX_MTLS_DEFAULT_TRUSTED_CA": mtls_material["ca"]})
    create_route(test_host, {"enforce_https": True, "mtls_require_client_certificate": True})

    restart_ceryx({})

    assert https_status(test_host, cert=mtls_material["client"]) == 500


def test_unreadable_default_ca_fails_requests_and_api_calls(
    backend, restart_ceryx, test_host, mtls_material
):
    restart_ceryx({"CERYX_MTLS_DEFAULT_TRUSTED_CA": mtls_material["ca"]})
    create_route(test_host, {"enforce_https": True, "mtls_require_client_certificate": True})

    restart_ceryx({"CERYX_MTLS_DEFAULT_TRUSTED_CA": "/does/not/exist/client-ca.pem"})

    assert https_status(test_host, cert=mtls_material["client"]) == 500
    response = update_route(test_host, {"mode": "proxy"}, expected=500)
    assert "CERYX_MTLS_DEFAULT_TRUSTED_CA" in response["detail"]


def test_malformed_default_depth_fails_api_calls(
    backend, restart_ceryx, test_host, mtls_material
):
    restart_ceryx({"CERYX_MTLS_DEFAULT_VERIFY_DEPTH": "two"})

    response = create_route(test_host, mtls(mtls_material["ca"]), expected=500)
    assert "CERYX_MTLS_DEFAULT_VERIFY_DEPTH" in response["detail"]


def test_malformed_route_settings_default_fails_route_creation(
    backend, restart_ceryx, test_host
):
    restart_ceryx({"CERYX_ROUTE_SETTINGS_DEFAULT_ENFORCE_HTTPS": "yes"})

    response = create_route(test_host, expected=500)
    assert "CERYX_ROUTE_SETTINGS_DEFAULT_ENFORCE_HTTPS" in response["detail"]


def test_mtls_default_without_a_default_ca_fails_route_creation(
    backend, restart_ceryx, test_host
):
    restart_ceryx({
        "CERYX_ROUTE_SETTINGS_DEFAULT_ENFORCE_HTTPS": "true",
        "CERYX_ROUTE_SETTINGS_DEFAULT_MTLS_REQUIRE_CLIENT_CERTIFICATE": "true",
    })

    response = create_route(test_host, expected=400)
    assert "CERYX_MTLS_DEFAULT_TRUSTED_CA" in response["detail"]


def test_mtls_default_without_the_https_default_fails_route_creation(
    backend, restart_ceryx, test_host, mtls_material
):
    restart_ceryx({
        "CERYX_ROUTE_SETTINGS_DEFAULT_MTLS_REQUIRE_CLIENT_CERTIFICATE": "true",
        "CERYX_MTLS_DEFAULT_TRUSTED_CA": mtls_material["ca"],
    })

    response = create_route(test_host, expected=400)
    assert "enforce_https" in response["detail"]
