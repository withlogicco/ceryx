import responder

from ceryx.db import RedisClient

api = responder.API()
client = RedisClient.from_config()

@api.route("/api/routes/")
async def list_routes(req, resp):
    resp.media = ["test"]

if __name__ == '__main__':
    api.run()