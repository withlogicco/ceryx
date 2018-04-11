from apistar import types, validators


class RouteWithoutSource(types.Type):
    target = validators.String()
    settings = validators.Object(
        properties={
            'enforce_https': validators.Boolean(default=False),
        },
        default={
            'enforce_https': False,
        },
    )


class Route(RouteWithoutSource):
    source = validators.String()
    target = validators.String()
    settings = validators.Object(
        properties={
            'enforce_https': validators.Boolean(default=False),
        },
        default={
            'enforce_https': False,
        },
    )
