import atexit
import os
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import redis

from utils import CERYX_ROOT, LE_STAGING_CA, SQLITE_TEST_DB

NGINX_BIN = os.environ.get("CERYX_TEST_NGINX_BIN", "nginx")
# The tests render the templates of the checkout they live in (the main
# checkout or a local clone) into a temporary directory, the same way the
# entrypoint renders them into /etc, and never write into the checkout.
TEMPLATES_DIR = os.path.join(CERYX_ROOT, "templates")
CONFIG_ROOT = tempfile.mkdtemp(prefix="ceryx-test-config-")
atexit.register(shutil.rmtree, CONFIG_ROOT, ignore_errors=True)
NGINX_CONF = os.path.join(CONFIG_ROOT, "nginx", "nginx.conf")
NGINX_ERROR_LOG = os.path.join(CONFIG_ROOT, "nginx-stderr.log")
CERYX_TEST_SERVICE = os.environ.get("CERYX_HOST", "ceryx")
API_HEALTH_URL = (
    os.environ.get("CERYX_TEST_API_URL", f"http://{CERYX_TEST_SERVICE}:8080")
    + "/api/routes"
)


def redis_test_client():
    host = os.environ.get("CERYX_REDIS_HOST", "redis")
    # Like Ceryx, treat an empty password as no password.
    password = os.environ.get("CERYX_REDIS_PASSWORD") or None
    try:
        return redis.Redis(host=host, password=password, protocol=2)
    except TypeError:
        return redis.Redis(host=host, password=password)


def pytest_configure(config):
    config.addinivalue_line("markers", "redis: tests that run against Redis")
    config.addinivalue_line("markers", "sqlite: tests that run against SQLite")
    config.addinivalue_line("markers", "integration: tests that require Ceryx/NGINX")
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end tests that require external network/public DNS setup",
    )
    config.addinivalue_line(
        "markers", "lets_encrypt: tests that exercise Let's Encrypt ACME flows"
    )
    configure_lets_encrypt_staging(config)



def configure_lets_encrypt_staging(config):
    """Enable Let's Encrypt staging for `CERYX_LE_STAGING_DOMAIN=... pytest -m lets_encrypt`.

    Runs before NGINX starts and before the test client reads its host
    suffixes, and only when the run selects lets_encrypt, so other runs keep
    Let's Encrypt disabled.
    """
    domain = os.environ.get("CERYX_LE_STAGING_DOMAIN")
    markexpr = config.option.markexpr or ""
    if not domain or "lets_encrypt" not in markexpr or "not lets_encrypt" in markexpr:
        return
    os.environ["CERYX_DISABLE_LETS_ENCRYPT"] = "false"
    os.environ["CERYX_LETS_ENCRYPT_CA"] = LE_STAGING_CA
    suffixes = os.environ.get("CERYX_TEST_HOST_SUFFIXES", ".ceryx.test")
    os.environ["CERYX_TEST_HOST_SUFFIXES"] = f"{suffixes},{domain}"


def clear_sqlite_database():
    if not os.path.exists(SQLITE_TEST_DB):
        return

    conn = sqlite3.connect(SQLITE_TEST_DB)
    try:
        conn.execute("DELETE FROM resource")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()


def wait_for_ceryx(timeout=20, url=API_HEALTH_URL, process=None):
    """Wait until the API answers; stop early if process (NGINX) exits."""
    import requests

    deadline = time.time() + timeout
    while time.time() < deadline:
        if process is not None and process.poll() is not None:
            return False
        try:
            response = requests.get(url, timeout=1)
            if response.status_code < 500:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False


def stop_ceryx_process(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def kill_stray_ceryx_processes():
    subprocess.run(["pkill", "-x", "nginx"], check=False)
    for port in (8080, 80, 443, 8999):
        if shutil.which("fuser"):
            subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )


def render_nginx_config(env):
    """Render every template to the same path under CONFIG_ROOT."""
    arguments = ["/usr/local/bin/dockerize"]
    for directory, _, files in os.walk(TEMPLATES_DIR):
        for name in sorted(files):
            template = os.path.join(directory, name)
            destination = os.path.join(
                CONFIG_ROOT, os.path.relpath(template, TEMPLATES_DIR)
            )
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            arguments += ["-template", f"{template}:{destination}"]

    subprocess.run(
        arguments,
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@pytest.fixture(scope="session")
def ceryx_processes():
    processes = {}
    yield processes

    if not processes:
        return

    for process in processes.values():
        stop_ceryx_process(process)
    kill_stray_ceryx_processes()


def auto_start_ceryx():
    """Whether the tests start Ceryx themselves, rather than use a running one."""
    return os.environ.get("CERYX_TEST_AUTO_START", "true").lower() not in {"0", "false", "no"}


def ensure_ceryx_running(backend_type, ceryx_processes, settings=None):
    """Make sure Ceryx runs with backend_type and settings.

    settings: environment variables for Ceryx on top of the tests' own, e.g. to
    enable Let's Encrypt. The tests restart Ceryx when either changes.
    """
    if not auto_start_ceryx():
        if not wait_for_ceryx():
            raise RuntimeError(f"Ceryx is not reachable for {backend_type} backend")
        return

    settings = settings or {}
    configuration = repr((backend_type, sorted(settings.items())))
    current_configuration = os.environ.get("CERYX_TEST_RUNNING_CONFIGURATION")
    if current_configuration == configuration and wait_for_ceryx(timeout=1):
        return

    for process in ceryx_processes.values():
        stop_ceryx_process(process)
    ceryx_processes.clear()
    kill_stray_ceryx_processes()

    os.makedirs(os.path.dirname(SQLITE_TEST_DB), exist_ok=True)
    os.makedirs("/usr/local/share/certificates", exist_ok=True)

    env = os.environ.copy()
    env.update(
        {
            "CERYX_STORAGE_BACKEND": backend_type,
            "CERYX_SQLITE_PATH": SQLITE_TEST_DB,
            "CERYX_REDIS_HOST": env.get("CERYX_REDIS_HOST", "redis"),
            "CERYX_DEBUG": env.get("CERYX_DEBUG", "true"),
            "CERYX_DISABLE_LETS_ENCRYPT": env.get("CERYX_DISABLE_LETS_ENCRYPT", "true"),
            "CERYX_LUALIB_DIR": env.get(
                "CERYX_LUALIB_DIR", os.path.join(CERYX_ROOT, "nginx", "lualib")
            ),
            "CERYX_STATIC_DIR": env.get(
                "CERYX_STATIC_DIR", os.path.join(CERYX_ROOT, "static")
            ),
        }
    )
    env.update(settings)

    render_nginx_config(env)

    process = subprocess.Popen(
        [
            NGINX_BIN,
            "-c",
            NGINX_CONF,
            "-g",
            "daemon off;",
        ],
        cwd=CERYX_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=open(NGINX_ERROR_LOG, "w"),
    )
    ceryx_processes[backend_type] = process
    os.environ["CERYX_TEST_RUNNING_CONFIGURATION"] = configuration

    if not wait_for_ceryx(process=process):
        stop_ceryx_process(process)
        ceryx_processes.pop(backend_type, None)
        os.environ.pop("CERYX_TEST_RUNNING_CONFIGURATION", None)
        with open(NGINX_ERROR_LOG) as error_log:
            errors = error_log.read()[-2000:]
        raise RuntimeError(f"Ceryx did not start for {backend_type} backend:\n{errors}")


class MockUpstreamHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for mock upstream server"""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("X-Test-Header", "mock-upstream")
        self.end_headers()
        self.wfile.write(b"Mock upstream response")

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Received: " + body)

    def log_message(self, format, *args):
        # Suppress logging
        pass


@pytest.fixture(scope="session", autouse=True)
def cleanup_sqlite_session():
    """Clear the shared SQLite test database at session boundaries."""
    clear_sqlite_database()
    yield
    clear_sqlite_database()


@pytest.fixture
def backend(request, ceryx_processes):
    """
    Backend fixture selected by the current test process environment.

    The same collected test node runs for every implementation/backend matrix
    entry. CI and Docker Compose set CERYX_STORAGE_BACKEND for one backend per
    pytest process so reports can merge one test row across all matrix columns.
    """
    backend_type = os.environ.get("CERYX_STORAGE_BACKEND", "redis")
    ensure_ceryx_running(backend_type, ceryx_processes)
    request.node.add_marker(getattr(pytest.mark, backend_type))
    request.node.add_marker(pytest.mark.integration)

    if backend_type == "redis":
        # Flush Redis database
        r = redis_test_client()
        r.flushdb()
    elif backend_type == "sqlite":
        os.makedirs(os.path.dirname(SQLITE_TEST_DB), exist_ok=True)
        clear_sqlite_database()

    yield backend_type

    # Cleanup after test
    if backend_type == "redis":
        r = redis_test_client()
        r.flushdb()
    elif backend_type == "sqlite":
        clear_sqlite_database()


@pytest.fixture
def restart_ceryx(backend, ceryx_processes):
    """Restart the tests' own Ceryx with extra environment variables.

    Skips with the Compose test stack, whose Ceryx the tests can't restart. The
    next test restarts Ceryx without them.
    """
    if not auto_start_ceryx():
        pytest.skip("Needs a Ceryx the tests start themselves.")

    def restart(settings):
        ensure_ceryx_running(backend, ceryx_processes, settings)

    return restart


# Let's Encrypt enabled, with a certificate authority that is never reached:
# the tests that use it put Let's Encrypt state in storage themselves.
LETS_ENCRYPT_SETTINGS = {
    "CERYX_DISABLE_LETS_ENCRYPT": "false",
    "CERYX_LETS_ENCRYPT_CA": "http://127.0.0.1:9/directory",
}


@pytest.fixture
def lets_encrypt_host(backend, ceryx_processes):
    """Host of a Ceryx with Let's Encrypt enabled, on the tests' storage.

    The Compose test stack runs one as a separate service, named by
    CERYX_TEST_LETS_ENCRYPT_HOST. Otherwise the tests restart their own Ceryx
    with Let's Encrypt enabled, and the next test restarts it without.
    """
    host = os.environ.get("CERYX_TEST_LETS_ENCRYPT_HOST")
    if host:
        if not wait_for_ceryx(url=f"http://{host}:8080/api/routes"):
            raise RuntimeError(f"{host} is not reachable")
        return host

    if not auto_start_ceryx():
        pytest.skip("Needs a Ceryx with Let's Encrypt enabled: set CERYX_TEST_LETS_ENCRYPT_HOST.")

    ensure_ceryx_running(backend, ceryx_processes, LETS_ENCRYPT_SETTINGS)
    return CERYX_TEST_SERVICE


@pytest.fixture
def mock_upstream():
    """
    Start a mock HTTP server in a background thread.
    Returns the URL of the mock server.
    """
    # Find an available port by binding to port 0
    server = HTTPServer(("0.0.0.0", 0), MockUpstreamHandler)
    port = server.server_port

    # Start server in background thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Give server time to start
    time.sleep(0.1)

    url = f"http://{socket.gethostname()}:{port}"

    yield url

    # Shutdown server
    server.shutdown()
    thread.join(timeout=1)


@pytest.fixture
def test_host():
    """Generate a unique test hostname"""
    return f"{uuid.uuid4()}.ceryx.test"


@pytest.fixture
def redis_client():
    """Get Redis client for direct backend manipulation"""
    return redis_test_client()
