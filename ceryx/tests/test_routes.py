import os

import requests

CERYX_API_URL = os.getenv("CERYX_API_URL", "http://api:5555")
CERYX_API_ROUTES_ROOT = os.path.join(CERYX_API_URL, "api/routes")

CERYX_HOST = "http://ceryx"


def test_no_route():
    """
    Ceryx should send a `503` response when receiving a request with a `Host`
    header that has not been registered for routing.
    """
    response = requests.get(
        CERYX_HOST, headers={"Host": "i-do-not-exist.ceryx.test"}
    )
    assert response.status_code == 503


def test_proxy():
    """
    Ceryx should successfully proxy the upstream request to the client, for a
    registered route.
    """
    api_upstream_host = "api"
    ceryx_route_source = "api.ceryx.test"
    ceryx_route_target = f"http://{api_upstream_host}:5555/api/routes"

    # Register the local Ceryx API as a route
    register_api_response = requests.post(
        CERYX_API_ROUTES_ROOT,
        json={"source": ceryx_route_source, "target": ceryx_route_target},
    )

    upstream_response = requests.get(
        ceryx_route_target, headers={"Host": api_upstream_host}
    )
    ceryx_response = requests.get(
        f"{CERYX_HOST}", headers={"Host": ceryx_route_source}
    )

    assert upstream_response.status_code == ceryx_response.status_code
    assert upstream_response.content == ceryx_response.content


def test_redirect():
    """
    Ceryx should respond with 301 status and the appropriate `Location` header
    for redirected routes.
    """
    api_upstream_host = "api"
    ceryx_route_target = "http://api:5555/api/routes"
    ceryx_route_source = "redirected-api.ceryx.test"

    # Register the local Ceryx API as a route
    register_api_response = requests.post(
        CERYX_API_ROUTES_ROOT,
        json={
            "source": ceryx_route_source,
            "target": ceryx_route_target,
            "settings": {"mode": "redirect"},
        },
    )

    original_url = f"{CERYX_HOST}/some/path/?some=args&more=args"
    target_url = f"{ceryx_route_target}/some/path/?some=args&more=args"

    ceryx_response = requests.get(
        original_url, headers={"Host": ceryx_route_source}, allow_redirects=False,
    )
    
    assert ceryx_response.status_code == 301
    assert ceryx_response.headers["Location"] == target_url


def test_enforce_https():
    """
    Ceryx should respond with 301 status and the appropriate `Location` header
    for routes with HTTPS enforced.
    """
    api_upstream_host = "api"
    api_upstream_target = "http://api:5555/"
    ceryx_route_source = "secure-api.ceryx.test"

    # Register the local Ceryx API as a route
    register_api_response = requests.post(
        CERYX_API_ROUTES_ROOT,
        json={
            "source": ceryx_route_source,
            "target": api_upstream_target,
            "settings": {"enforce_https": True},
        },
    )


    original_url = f"{CERYX_HOST}/some/path/?some=args&more=args"
    secure_url = f"https://{ceryx_route_source}/some/path/?some=args&more=args"
    ceryx_response = requests.get(
        original_url, headers={"Host": ceryx_route_source}, allow_redirects=False,
    )

    assert ceryx_response.status_code == 301
    assert ceryx_response.headers["Location"] == secure_url
