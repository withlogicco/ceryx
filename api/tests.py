import uuid

import pytest

from api import api
from ceryx import schemas


@pytest.fixture
def client():
    return api.requests


@pytest.fixture
def host():
    return f"{uuid.uuid4()}.api.ceryx.test"


def test_list_routes(client, host):
    """
    Assert that listing routes will return a JSON list.
    """
    route_1 = schemas.Route.validate({
        "source": f"route-1-{host}",
        "target": "http://somewhere",
    })
    client.post("/api/routes/", json=dict(route_1))

    route_2 = schemas.Route.validate({
        "source": f"route-2-{host}",
        "target": "http://somewhere",
    })
    client.post("/api/routes/", json=dict(route_2))

    response = client.get("/api/routes/")
    assert response.status_code == 200

    route_list = response.json()
    assert dict(route_1) in route_list
    assert dict(route_2) in route_list


def test_create_route(client, host):
    """
    Assert that creating a route, will result in the appropriate route.
    """
    route = schemas.Route.validate({
        "source": host,
        "target": "http://somewhere",
    })

    # Create a route and assert valid data in response
    response = client.post("/api/routes/", json=dict(route))
    assert response.status_code == 201
    assert response.json() == dict(route)

    # Also get the route and assert valid data
    response = client.get(f"/api/routes/{host}/")
    assert response.status_code == 200
    assert response.json() == dict(route)


def test_update_route(client, host):
    """
    Assert that creating a route, will result in the appropriate route.
    """
    route = schemas.Route.validate({
        "source": host,
        "target": "http://somewhere",
    })

    client.post("/api/routes/", json=dict(route))

    updated_route = schemas.Route.validate({
        "source": host,
        "target": "http://somewhere-else",
    })
    updated_route_payload = dict(updated_route)
    del updated_route_payload["source"]  # We should not need that
    response = client.put(f"/api/routes/{host}/", json=updated_route_payload)

    # Also get the route and assert valid data
    assert response.status_code == 200
    assert response.json() == dict(updated_route)


def test_delete_route(client, host):
    """
    Assert that deleting a route, will actually delete it.
    """
    route = schemas.Route.validate({
        "source": host,
        "target": "http://somewhere",
    })

    # Create a route
    client.post("/api/routes/", json=dict(route))

    # Delete the route
    response = client.delete(f"/api/routes/{host}/")
    assert response.status_code == 204

    # Also get the route and assert that it does not exist
    response = client.get(f"/api/routes/{host}/")
    assert response.status_code == 404

