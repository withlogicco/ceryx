import typing

from apistar import App, http, Route

from ceryx import types
from ceryx.db import RedisRouter


ROUTER = RedisRouter.from_config()


def list_routes() -> typing.List[types.Route]:
    routes = ROUTER.lookup_routes()
    return [types.Route(route) for route in routes]


def create_route(route: types.Route) -> types.Route:
    ROUTER.insert(**route)
    return http.JSONResponse(route, status_code=201)


def update_route(source: str, route: types.RouteWithoutSource) -> types.Route:
    ROUTER.insert(source, **route)
    updated_route = dict(source=source, **route)
    return types.Route(updated_route)


def get_route(source: str) -> types.Route:
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


def delete_route(source: str) -> types.Route:
    try:
        route = {
            'source': source,
            'target': ROUTER.lookup(source),
            'settings': ROUTER.lookup_settings(source),
        }
        ROUTER.delete(source)
        return http.JSONResponse(
            types.Route(route),
            status_code=204,
        )
    except RedisRouter.LookupNotFound:
        return http.JSONResponse(
            {'message': f'Route with source {source} doesn\'t exist'},
            status_code=404,
        )


routes = [
    Route('/api/routes', method='GET', handler=list_routes),
    Route('/api/routes', method='POST', handler=create_route),
    Route('/api/routes/{source}', method='GET', handler=get_route),
    Route('/api/routes/{source}', method='PUT', handler=update_route),
    Route('/api/routes/{source}', method='DELETE', handler=delete_route),

    # Allow trailing slashes as well (GitHub style)
    Route('/api/routes/', method='GET', handler=list_routes, name='list_routes_trailing_slash'),
    Route('/api/routes/', method='POST', handler=create_route, name='create_route_trailing_slash'),
    Route('/api/routes/{source}/', method='GET', handler=get_route, name='get_route_trailing_slash'),
    Route('/api/routes/{source}/', method='PUT', handler=update_route, name='update_route_trailing_slash'),
    Route('/api/routes/{source}/', method='DELETE', handler=delete_route, name='delete_route_trailing_slash'),
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