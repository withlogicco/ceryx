"""HTTP/2 on the TLS listener, with HTTP/1.1 compatibility."""

import base64
import concurrent.futures
import hashlib
import json
import os
import socket
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

import pytest
import requests

from utils import (
    ceryx_api_url,
    create_certificates_for_host,
    pem_fingerprint,
    served_certificate_fingerprint,
)

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


@pytest.fixture
def echo_upstream():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"path": self.path, "host": self.headers.get("Host"),
                               "proto": self.headers.get("X-Forwarded-Proto"),
                               "forwarded_for": self.headers.get("X-Forwarded-For")}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://{socket.gethostname()}:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def request(host, path="/", *, version="--http2", cert=None, scheme="https", client_cert=None):
    destination = os.environ.get("CERYX_HOST", "ceryx")
    port = 443 if scheme == "https" else 80
    command = ["curl", "--silent", "--show-error", "--noproxy", "*", "--max-time", "10",
               version, "--connect-to", f"{host}:{port}:{destination}:{port}",
               "--dump-header", "-", "--write-out", "\nCERYX_RESULT:%{http_version}:%{http_code}"]
    if scheme == "https":
        command.extend(["--cacert", cert] if cert else ["--insecure"])
    if client_cert:
        command.extend(["--cert", client_cert[0], "--key", client_cert[1]])
    command.append(f"{scheme}://{host}{path}")
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    response, metadata = result.stdout.rsplit("\nCERYX_RESULT:", 1)
    version, status = metadata.split(":")
    headers, body = response.split("\r\n\r\n", 1) if "\r\n\r\n" in response else response.split("\n\n", 1)
    return version, int(status), headers, body


def peer_certificate(host):
    return served_certificate_fingerprint(host, alpn="h2")


def fingerprint(path):
    with open(path) as cert:
        return pem_fingerprint(cert.read())


def put_route(host, target, **extra):
    response = requests.post(ceryx_api_url("/api/routes"), json={"source": host, "target": target, **extra}, timeout=10)
    assert response.status_code == 201, response.text


def test_http2_routing_and_http1_fallback(backend, test_host, echo_upstream):
    put_route(test_host, echo_upstream)
    version, status, headers, body = request(test_host, "/some/path?one=two")
    assert (version, status) == ("2", 200)
    data = json.loads(body)
    assert data["path"] == "/some/path?one=two"
    assert data["host"] == test_host
    assert data["proto"] == "https"
    assert data["forwarded_for"]
    assert "server: nginx/" not in headers.lower()
    assert request(test_host, version="--http1.1")[:2] == ("1.1", 200)
    assert request(test_host, scheme="http", version="--http1.1")[:2] == ("1.1", 200)
    missing_version, missing_status, missing_headers, _ = request("unknown-http2.ceryx.test")
    assert (missing_version, missing_status) == ("2", 503)
    assert "server: nginx" in missing_headers.lower()
    assert "server: nginx/" not in missing_headers.lower()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda n: request(test_host, f"/parallel/{n}"), range(4)))
    assert [json.loads(r[3])["path"] for r in results] == [f"/parallel/{n}" for n in range(4)]
    assert all(r[:2] == ("2", 200) for r in results)


def test_http2_route_mutations_and_redirect(backend, test_host, echo_upstream):
    put_route(test_host, echo_upstream)
    assert request(test_host)[:2] == ("2", 200)
    target = "https://example.org"
    response = requests.put(ceryx_api_url(f"/api/routes/{test_host}"), json={"target": target, "settings": {"mode": "redirect"}}, timeout=10)
    assert response.status_code == 200
    version, status, headers, _ = request(test_host, "/path?x=1")
    assert (version, status) == ("2", 301)
    assert "location: https://example.org/path?x=1" in headers.lower()
    assert requests.delete(ceryx_api_url(f"/api/routes/{test_host}"), timeout=10).status_code == 204
    assert request(test_host)[:2] == ("2", 503)


def test_http2_certificate_mutations(backend, test_host, echo_upstream):
    put_route(test_host, echo_upstream)
    fallback = peer_certificate(test_host)
    cert, key = create_certificates_for_host(test_host)
    def payload():
        with open(cert) as certificate, open(key) as private_key:
            return {"domain": test_host, "certificate": certificate.read(), "private_key": private_key.read()}
    url = ceryx_api_url("/api/certificates")
    assert requests.post(url, json=payload(), timeout=10).status_code == 201
    assert peer_certificate(test_host) == fingerprint(cert)
    assert request(test_host, cert=cert)[:2] == ("2", 200)
    old = fingerprint(cert)
    create_certificates_for_host(test_host)
    assert requests.post(url, json=payload(), timeout=10).status_code == 201
    assert fingerprint(cert) != old
    assert peer_certificate(test_host) == fingerprint(cert)
    assert request(test_host, cert=cert)[:2] == ("2", 200)
    assert requests.delete(f"{url}/{test_host}", timeout=10).status_code == 204
    assert peer_certificate(test_host) == fallback
    assert request(test_host)[:2] == ("2", 200)


def test_cleartext_http2_is_not_enabled(backend):
    with socket.create_connection((os.environ.get("CERYX_HOST", "ceryx"), 80), timeout=10) as connection:
        connection.settimeout(10)
        connection.sendall(b"PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n")
        response = connection.recv(1024)
    assert response.startswith(b"HTTP/1.1 400")


def test_http2_certificate_precedence(backend, test_host, echo_upstream):
    wildcard_cert, wildcard_key = create_certificates_for_host("wildcard.ceryx.test")
    host_cert, host_key = create_certificates_for_host(test_host)
    put_route("$wildcard", echo_upstream, settings={"certificate_path": wildcard_cert, "key_path": wildcard_key})
    assert peer_certificate(test_host) == fingerprint(wildcard_cert)
    put_route(test_host, echo_upstream, settings={"certificate_path": host_cert, "key_path": host_key})
    assert peer_certificate(test_host) == fingerprint(host_cert)
    assert request(test_host, cert=host_cert)[:2] == ("2", 200)


def test_http1_websocket_upgrade(backend, test_host):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            assert self.headers.get("Upgrade", "").lower() == "websocket"
            assert self.headers.get("Connection", "").lower() == "upgrade"
            key = self.headers["Sec-WebSocket-Key"]
            accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.wfile.flush()
            frame = self.rfile.read(12)
            assert frame[:6] == b"\x81\x86mask"
            payload = bytes(value ^ b"mask"[index % 4] for index, value in enumerate(frame[6:]))
            self.wfile.write(b"\x81\x06" + payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        put_route(test_host, f"http://{socket.gethostname()}:{server.server_port}")
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.set_alpn_protocols(["http/1.1"])
        with socket.create_connection((os.environ.get("CERYX_HOST", "ceryx"), 443), timeout=10) as raw:
            with context.wrap_socket(raw, server_hostname=test_host) as connection:
                connection.settimeout(10)
                assert connection.selected_alpn_protocol() == "http/1.1"
                connection.sendall(f"GET / HTTP/1.1\r\nHost: {test_host}\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n".encode())
                headers = b""
                while b"\r\n\r\n" not in headers:
                    chunk = connection.recv(4096)
                    assert chunk, "connection closed before upgrade"
                    headers += chunk
                assert headers.startswith(b"HTTP/1.1 101")
                assert b"Sec-WebSocket-Accept: s3pPLMBiTxaQ9kYGzzhZRbK+xOo=" in headers
                payload = b"hello!"
                masked = bytes(value ^ b"mask"[index % 4] for index, value in enumerate(payload))
                connection.sendall(b"\x81\x86mask" + masked)
                reply = b""
                while len(reply) < 8:
                    chunk = connection.recv(8 - len(reply))
                    assert chunk, "connection closed before WebSocket reply"
                    reply += chunk
                assert reply == b"\x81\x06hello!"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
