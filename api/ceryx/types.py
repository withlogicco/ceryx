from apistar import types, validators


class Route(types.Type):
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
