import typing

from apistar import App, http, Route

from ceryx import types
from ceryx.db import RedisRouter


ROUTER = RedisRouter.from_config()


def list_routes() -> typing.List[types.Route]:
    routes = ROUTER.lookup_routes()
    return [types.Route(route) for route in routes]


def get_route(source: str) -> dict:
    try:
        resource = {
            'source': source,
            'target': ROUTER.lookup(source),
            'settings': ROUTER.lookup_settings(source),
        }
        return resource
    except RedisRouter.LookupNotFound:
        return http.JSONResponse(
            {'message': f'Route with source {source} doesn\'t exist'},
            status_code=404,
        )


routes = [
    Route('/api/routes/', method='GET', handler=list_routes),
    Route('/api/routes/{source}/', method='GET', handler=get_route),
]

app = App(routes=routes)

if __name__ == '__main__':
    from ceryx import settings

    app.serve(
        settings.API_BIND_HOST,
        settings.API_BIND_PORT,
        use_debugger=settings.DEBUG,
        use_reloader=settings.DEBUG,
    )