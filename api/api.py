import responder

from ceryx.db import RedisClient

api = responder.API()
client = RedisClient.from_config()

@api.route("/api/routes/")
async def list_routes(req, resp):
    resp.media = [dict(route) for route in client.list_routes()]

if __name__ == '__main__':
    api.run()