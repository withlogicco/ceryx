"""
Simple Redis client, implemented the data logic of Ceryx.
"""
import re

import redis

from ceryx import schemas
from ceryx import settings


STARTS_WITH_PROTOCOL = r"^https?://"


def _str(subject):
    return subject.decode("utf-8") if type(subject) == bytes else str(bytes)


def ensure_protocol(url):
    return url if re.match(STARTS_WITH_PROTOCOL, url) else f"http://{url}"


def encode_settings(settings):
    """
    Encode and sanitize settings in order to be written to Redis.
    """
    encoded_settings = {
        "enforce_https": str(int(settings.get("enforce_https", False))),
        "mode": settings.get("mode", "proxy"),
    }

    return encoded_settings


def decode_settings(settings):
    """
    Decode and sanitize settings from Redis, in order to transport via HTTP
    """

    # If any of the keys or values of the provided settings are bytes, then
    # convert them to strings.
    _settings = {_str(k): _str(v) for k, v in settings.items()}
    decoded = {
        "enforce_https": bool(int(_settings.get("enforce_https", "0"))),
        "mode": _settings.get("mode", "proxy"),
    }

    return decoded


class RedisClient:
    """
    Router using a redis backend, in order to route incoming requests.
    """

    class LookupNotFound(Exception):
        """
        Exception raised when a lookup for a specific host was not found.
        """

        def __init__(self, message, errors=None):
            Exception.__init__(self, message)
            self.errors = errors or {"message": message}

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
        )

    def __init__(self, host, port, password, db, prefix):
        self.client = redis.StrictRedis(host=host, port=port, password=password, db=db)
        self.prefix = prefix
    
    def _prefixed_key(self, key):
        return f"{self.prefix}:{key}"

    def _route_key(self, source):
        """
        Returns the prefixed key, if prefix has been defined, for the given
        route.
        """
        return self._prefixed_key(f"routes:{source}")

    def _settings_key(self, source):
        """
        Returns the prefixed key, if prefix has been defined, for the given
        source's setting.
        """
        return self._prefixed_key(f"settings:{source}")

    def delete_settings(self, source):
        settings_key = self._settings_key(source)
        self.client.delete(settings_key)

    def set_settings(self, source, settings):
        settings_key = self._settings_key(source)
        encoded_settings = encode_settings(settings or {})
        self.client.hmset(settings_key, encoded_settings)

    def lookup(self, host, silent=False):
        """
        Fetches the target host for the given host name. If no host matching
        the given name is found and silent is False, raises a LookupNotFound
        exception.
        """
        lookup_host = self._route_key(host)
        target_host = self.client.get(lookup_host)

        if target_host is None and not silent:
            raise RedisClient.LookupNotFound("Given host does not match with any route")
        else:
            return _str(target_host)

    def lookup_settings(self, host):
        """
        Fetches the settings of the given host name.
        """
        key = self._settings_key(host)
        settings = self.client.hgetall(key)
        decoded_settings = decode_settings(settings)
        return decoded_settings

    def lookup_hosts(self):
        """
        Return all hosts.
        """
        lookup_pattern = self._route_key("*")  # Base
        left_padding = len(lookup_pattern) - 1
        keys = self.client.keys(lookup_pattern)
        return [_str(key)[left_padding:] for key in keys]
    
    def get_route_for_host(self, host):
        route = {
            "source": host,
            "target": self.lookup(host, silent=True),
            "settings": self.lookup_settings(host),
        }
        return route

    def lookup_routes(self):
        """
        Return all routes
        """
        hosts = self.lookup_hosts()
        routes = [self.get_route_for_host(host) for host in hosts]
        return routes

    def insert(self, source, target, settings):
        """
        Inserts a new source/target host entry in to the database.
        """
        target = ensure_protocol(target)
        route_key = self._route_key(source)
        self.client.set(route_key, target)
        self.set_settings(source, settings)
        route = {"source": source, "target": target, "settings": settings}
        return route

    def delete(self, source):
        """
        Deletes the entry of the given source, if it exists.
        """
        source_key = self._route_key(source)
        self.client.delete(source_key)
        self.delete_settings(source)
