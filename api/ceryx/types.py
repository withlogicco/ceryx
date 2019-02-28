from apistar import types, validators


SETTINGS_VALIDATOR = validators.Object(
    properties={
        "enforce_https": validators.Boolean(default=False),
        "mode": validators.String(default="proxy", enum=["proxy", "redirect"]),
    },
    default={"enforce_https": False, "mode": "proxy"},
)


class RouteWithoutSource(types.Type):
    target = validators.String()
    settings = SETTINGS_VALIDATOR


class Route(types.Type):
    source = validators.String()
    target = validators.String()
    settings = SETTINGS_VALIDATOR
