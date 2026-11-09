import hashlib
import os
import socket
import ssl
import stat
import subprocess
from urllib.parse import urljoin

CERTIFICATE_ROOT = "/usr/local/share/certificates"
# The checkout these tests live in (the main checkout or a local clone).
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVERYBODY_CAN_READ = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH


def checkout_path(variable, default):
    """Path from an environment variable, or default.

    Relative values resolve against the checkout, not the working directory,
    so a shared env file can say ``src`` and mean this checkout's ``src/``.
    """
    return os.path.join(REPO_ROOT, os.environ.get(variable) or default)


# The test database is separate from the app's CERYX_SQLITE_PATH, so running
# the tests never touches the dev database.
SQLITE_TEST_DB = checkout_path("CERYX_TEST_SQLITE_PATH", "/var/lib/ceryx/test.db")
CERYX_ROOT = checkout_path("CERYX_TEST_ROOT", "src")
LE_STAGING_CA = "https://acme-staging-v02.api.letsencrypt.org/directory"
OPENAPI_SPEC = checkout_path("CERYX_TEST_OPENAPI_SPEC", "docs/openapi.yaml")


def ceryx_api_base_url():
    """Return the API origin for the Ceryx distribution under test."""
    return os.environ.get(
        "CERYX_TEST_API_URL",
        f"http://{os.environ.get('CERYX_HOST', 'ceryx')}:8080",
    ).rstrip("/")


def ceryx_api_url(path=""):
    """Build a Ceryx API URL from the configured API origin."""
    return urljoin(f"{ceryx_api_base_url()}/", path.lstrip("/"))


def served_certificate_fingerprint(host, alpn=None):
    """SHA-256 of the certificate Ceryx presents for host (SNI).

    With alpn, also offer that protocol and assert it was negotiated.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    if alpn:
        context.set_alpn_protocols([alpn])
    destination = os.environ.get("CERYX_HOST", "ceryx")
    with socket.create_connection((destination, 443), timeout=10) as raw:
        with context.wrap_socket(raw, server_hostname=host) as connection:
            if alpn:
                assert connection.selected_alpn_protocol() == alpn
            return hashlib.sha256(connection.getpeercert(binary_form=True)).hexdigest()


def pem_fingerprint(pem):
    """SHA-256 of a PEM certificate, comparable to served_certificate_fingerprint."""
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()


def create_certificates_for_host(host):
    base_path = f"{CERTIFICATE_ROOT}/{host}"
    certificate_path = f"{base_path}.crt"
    key_path = f"{base_path}.key"

    command = [
        "openssl",
        "req",
        "-x509",
        "-newkey",
        "rsa:4096",
        "-keyout",
        key_path,
        "-out",
        certificate_path,
        "-days",
        "1",
        "-subj",
        f"/C=GR/ST=Attica/L=Athens/O=SourceLair/OU=Org/CN={host}",
        "-addext",
        f"subjectAltName=DNS:{host}",
        "-nodes",
    ]
    subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    os.chmod(certificate_path, EVERYBODY_CAN_READ)
    os.chmod(key_path, EVERYBODY_CAN_READ)

    return certificate_path, key_path
