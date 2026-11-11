"""The API matches docs/openapi.yaml: routing, allowed methods and response bodies."""

import re
import uuid

import pytest
import requests
import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate as validate_openapi

from test_api_certificates import create_certificate_payload
from utils import OPENAPI_SPEC, ceryx_api_url

SPEC_PATH = OPENAPI_SPEC
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
# 405 is checked by test_undocumented_methods_return_405; 500 needs a broken backend.
NOT_EXERCISED_BY_SCENARIOS = {"405", "500"}


@pytest.fixture(scope="module")
def spec():
    with open(SPEC_PATH) as spec_file:
        return yaml.safe_load(spec_file)


def documented_methods(path_item):
    return {method.upper() for method in path_item if method.upper() in HTTP_METHODS}


def resolve(spec, node):
    while "$ref" in node:
        target = spec
        for part in node["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        node = target
    return node


def missing_name():
    # Outside ceryx.test, so no wildcard certificate from another test matches.
    return f"missing-{uuid.uuid4()}.contract.invalid"


def fill_path(template, value):
    return re.sub(r"\{[^}]+\}", value, template)


class Contract:
    """Sends requests and checks each response against the spec."""

    def __init__(self, spec):
        self.spec = spec
        self.exercised = set()

    def call(self, method, template, value="", **kwargs):
        operation = self.spec["paths"][template][method.lower()]
        response = requests.request(
            method, ceryx_api_url(fill_path(template, value)), timeout=10, **kwargs
        )
        status = str(response.status_code)

        assert status in operation["responses"], (
            f"{method} {template} returned undocumented {status}: {response.text}"
        )
        self.check_body(operation["responses"][status], response)
        self.exercised.add((method, template, status))
        return response

    def check_body(self, documented, response):
        documented = resolve(self.spec, documented)
        content = documented.get("content")
        if not content:
            assert response.content == b""
            return

        schema = content["application/json"]["schema"]
        validator = Draft202012Validator(
            {"allOf": [schema], "components": self.spec["components"]}
        )
        validator.validate(response.json())

    def assert_exercised(self, templates):
        documented = {
            (method.upper(), template, status)
            for template in templates
            for method, operation in self.spec["paths"][template].items()
            if method.upper() in HTTP_METHODS
            for status in operation["responses"]
            if status not in NOT_EXERCISED_BY_SCENARIOS
        }
        assert documented - self.exercised == set()


def test_spec_is_valid_openapi(spec):
    validate_openapi(spec)


def test_documented_operations_are_routed(backend, spec, test_host):
    contract = Contract(spec)
    for template, path_item in spec["paths"].items():
        for method in documented_methods(path_item):
            response = contract.call(method, template, test_host, json={})
            assert response.status_code != 405


def test_undocumented_methods_return_405(backend, spec, test_host):
    for template, path_item in spec["paths"].items():
        allowed = documented_methods(path_item)
        url = ceryx_api_url(fill_path(template, test_host))
        for method in sorted(set(HTTP_METHODS) - allowed):
            response = requests.request(method, url, timeout=10)
            assert response.status_code == 405, f"{method} {template}"
            allow = {item.strip() for item in response.headers["Allow"].split(",")}
            assert allow == allowed, f"{method} {template}"
            if method != "HEAD":
                assert "detail" in response.json()


def test_routes_contract(backend, spec, test_host, mock_upstream):
    contract = Contract(spec)
    collection, item = "/api/routes", "/api/routes/{host}"

    contract.call("GET", collection)
    contract.call(
        "POST",
        collection,
        json={"source": test_host, "target": mock_upstream, "settings": {"mode": "proxy"}},
    )
    contract.call("POST", collection, json={"source": test_host})
    contract.call("GET", item, test_host)
    contract.call("GET", item, missing_name())
    contract.call("PUT", item, test_host, json={"settings": {"enforce_https": True}})
    contract.call("PUT", item, test_host, json={"source": "other.ceryx.test"})
    contract.call("PUT", item, missing_name(), json={"target": mock_upstream})
    contract.call("DELETE", item, test_host)

    contract.assert_exercised([collection, item])


def test_certificates_contract(backend, spec, test_host):
    contract = Contract(spec)
    collection, item = "/api/certificates", "/api/certificates/{domain}"
    payload = create_certificate_payload(test_host)
    # GET falls back to certificate files in the $wildcard route settings. The
    # backend fixture flushes storage directly, so clear that route through the
    # API to also drop its cached settings from an earlier test.
    requests.delete(ceryx_api_url("/api/routes/$wildcard"), timeout=10)

    contract.call("POST", collection, json={**payload, "meta": {"vendor": "test"}})
    contract.call("POST", collection, json={"domain": test_host})
    contract.call("GET", collection)
    contract.call("GET", item, test_host)
    contract.call("GET", item, missing_name())
    contract.call("PUT", item, test_host, json={"meta": {"vendor": "manual"}})
    contract.call("PUT", item, test_host, json={"certificate": payload["certificate"]})
    contract.call("PUT", item, missing_name(), json=payload)
    contract.call("DELETE", item, test_host)

    contract.assert_exercised([collection, item])

