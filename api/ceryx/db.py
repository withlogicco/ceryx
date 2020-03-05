"""
Simple Redis client, implemented the data logic of Ceryx.
"""
import redis

from ceryx import exceptions, schemas, settings


def _str(subject):
    return subject.decode("utf-8") if type(subject) == bytes else str(bytes)


class RedisClient:
    @staticmethod
    def from_config(path=None):
        """
        Returns a RedisClient, using the default configuration from Ceryx
        settings.
        """
        return RedisClient(
            settings.REDIS_HOST,
            settings.REDIS_PORT,
            settings.REDIS_PASSWORD,
            0,
            settings.REDIS_PREFIX,
            settings.REDIS_TIMEOUT,
        )

    def __init__(self, host, port, password, db, prefix, timeout):
        self.client = redis.StrictRedis(host=host, port=port, password=password, db=db, socket_timeout=timeout, socket_connect_timeout=timeout)
        self.prefix = prefix
    
    def _prefixed_key(self, key):
        return f"{self.prefix}:{key}"

    def _route_key(self, source):
        return self._prefixed_key(f"routes:{source}")

    def _settings_key(self, source):
        return self._prefixed_key(f"settings:{source}")

    def _delete_target(self, source):
        key = self._route_key(source)
        self.client.delete(key)
    
    def _delete_settings(self, source):
        key = self._settings_key(source)
        self.client.delete(key)

    def _lookup_target(self, source, raise_exception=False):
        key = self._route_key(source)
        target = self.client.get(key)

        if target is None and raise_exception:
            raise exceptions.NotFound("Route not found.")
        
        return target

    def _lookup_settings(self, source):
        key = self._settings_key(source)
        return self.client.hgetall(key)

    def lookup_sources(self, pattern="*"):
        lookup_pattern = self._route_key(pattern)
        left_padding = len(lookup_pattern) - 1
        keys = self.client.keys(lookup_pattern)
        return [_str(key)[left_padding:] for key in keys]
    
    def _set_target(self, source, target, ttl=None):
        key = self._route_key(source)
        self.client.set(key, target, ex=ttl)

    def _set_settings(self, source, settings):
        key = self._settings_key(source)
        self.client.hmset(key, settings)
    
    def _set_route(self, route: schemas.Route):
        redis_data = route.to_redis()
        self._set_target(route.source, redis_data["target"], route.settings.get("ttl"))
        self._set_settings(route.source, redis_data["settings"])
        return route
    
    def get_route(self, source):
        target = self._lookup_target(source, raise_exception=True)
        settings = self._lookup_settings(source)
        route = schemas.Route.from_redis({
            "source": source,
            "target": target,
            "settings": settings
        })
        return route

    def list_routes(self):
        sources = self.lookup_sources()
        routes = [self.get_route(source) for source in sources]
        return routes
    
    def create_route(self, data: dict):
        route = schemas.Route.validate(data)
        return self._set_route(route)
    
    def update_route(self, source: str, data: dict):
        data["source"] = source
        route = schemas.Route.validate(data)
        return self._set_route(route)

    def delete_route(self, source: str):
        self._delete_target(source)
        self._delete_settings(source)
