import responder

from ceryx.db import RedisClient
from ceryx.exceptions import NotFound


api = responder.API()
client = RedisClient.from_config()


@api.route("/", default=True)
def default(req, resp):
    if not req.url.path.endswith("/"):
        api.redirect(resp, f"{req.url.path}/")

@api.route("/api/routes/")
class RouteListView:
    async def on_get(self, req, resp):
        resp.media = [dict(route) for route in client.list_routes()]

    async def on_post(self, req, resp):
        data = await req.media()
        route = client.create_route(data)
        resp.status_code = api.status_codes.HTTP_201
        resp.media = dict(route)


@api.route("/api/routes/{host}/")
class RouteDetailView:
    async def on_get(self, req, resp, *, host: str):
        try:
            route = client.get_route(host)
            resp.media = dict(route)
        except NotFound:
            resp.media = {"detail": f"No route found for {host}."}
            resp.status_code = 404

    async def on_put(self, req, resp, *, host: str):
        data = await req.media()
        route = client.update_route(host, data)
        resp.media = dict(route)
    
    async def on_delete(self, req, resp, *, host:str):
        client.delete_route(host)
        resp.status_code = api.status_codes.HTTP_204


if __name__ == '__main__':
    api.run()