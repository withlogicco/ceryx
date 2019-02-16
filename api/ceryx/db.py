"""
Simple Redis client, implemented the data logic of Ceryx.
"""
import redis

from ceryx import settings


def _str(subject):
    return subject.decode('utf-8') if type(subject) == bytes else str(bytes)


def encode_settings(settings):
    """
    Encode and sanitize settings in order to be written to Redis.
    """
    encoded_settings = {
        'enforce_https': str(int(settings.get('enforce_https', False))),
        'mode': settings.get('mode', 'proxy'),
    }

    return encoded_settings


def decode_settings(settings):
    """
    Decode and sanitize settings from Redis, in order to transport via HTTP
    """

    # If any of the keys or values of the provided settings are bytes, then
    # convert them to strings.
    _settings = {
        _str(k): _str(v) for k, v in settings.items()
    }
    decoded = {
        'enforce_https': bool(int(_settings.get('enforce_https', '0'))),
        'mode': _settings.get('mode', 'proxy'),
    }

    return decoded


class RedisRouter(object):
    """
    Router using a redis backend, in order to route incoming requests.
    """
    class LookupNotFound(Exception):
        """
        Exception raised when a lookup for a specific host was not found.
        """

        def __init__(self, message, errors=None):
            Exception.__init__(self, message)
            if errors is None:
                self.errors = {'message': message}
            else:
                self.errors = errors

    @staticmethod
    def from_config(path=None):
        """
        Returns a RedisRouter, using the default configuration from Ceryx
        settings.
        """
        return RedisRouter(settings.REDIS_HOST, settings.REDIS_PORT,
                           settings.REDIS_PASSWORD, 0, settings.REDIS_PREFIX)

    def __init__(self, host, port, password, db, prefix):
        self.client = redis.StrictRedis(
            host=host, port=port, password=password, db=db)
        self.prefix = prefix

    def _prefixed_route_key(self, source):
        """
        Returns the prefixed key, if prefix has been defined, for the given
        route.
        """
        prefixed_key = 'routes:%s'
        if self.prefix is not None:
            prefixed_key = self.prefix + ':routes:%s'
        prefixed_key = prefixed_key % source
        return prefixed_key

    def _prefixed_settings_key(self, source):
        """
        Returns the prefixed key, if prefix has been defined, for the given
        source's setting.
        """
        prefixed_key = 'settings:%s'
        if self.prefix is not None:
            prefixed_key = self.prefix + ':settings:%s'
        prefixed_key = prefixed_key % source
        return prefixed_key
    
    def _delete_settings_for_source(self, source):
        settings_key = self._prefixed_settings_key(source)
        self.client.delete(settings_key)
    
    def _set_settings_for_source(self, source, settings):
        settings_key = self._prefixed_settings_key(source)

        if settings:
            encoded_settings = encode_settings(settings)
            self.client.hmset(settings_key, encoded_settings)
        else:
            self._delete_settings_for_source(source)

    def lookup(self, host, silent=False):
        """
        Fetches the target host for the given host name. If no host matching
        the given name is found and silent is False, raises a LookupNotFound
        exception.
        """
        lookup_host = self._prefixed_route_key(host)
        target_host = self.client.get(lookup_host)

        if target_host is None and not silent:
            raise RedisRouter.LookupNotFound(
                'Given host does not match with any route'
            )
        else:
            return _str(target_host)

    def lookup_settings(self, host):
        """
        Fetches the settings of the given host name.
        """
        key = self._prefixed_settings_key(host)
        settings = self.client.hgetall(key)
        decoded_settings = decode_settings(settings)
        return decoded_settings

    def lookup_hosts(self, pattern):
        """
        Fetches hosts that match the given pattern. If no pattern is given,
        all hosts are returned.
        """
        if not pattern:
            pattern = '*'
        lookup_pattern = self._prefixed_route_key(pattern)
        keys = self.client.keys(lookup_pattern)
        filtered_keys = [key[len(lookup_pattern) - len(pattern):] for key in keys]
        return [_str(key) for key in filtered_keys]

    def lookup_routes(self, pattern='*'):
        """
        Fetches routes with host that matches the given pattern. If no pattern
        is given, all routes are returned.
        """
        hosts = self.lookup_hosts(pattern)
        routes = []
        for host in hosts:
            routes.append(
                {
                    'source': host,
                    'target': self.lookup(host, silent=True),
                    'settings': self.lookup_settings(host),
                }
            )
        return routes

    def insert(self, source, target, settings):
        """
        Inserts a new source/target host entry in to the database.
        """
        route_key = self._prefixed_route_key(source)
        self.client.set(route_key, target)
        self._set_settings_for_source(source, settings)

    def delete(self, source):
        """
        Deletes the entry of the given source, if it exists.
        """
        source_key = self._prefixed_route_key(source)
        self.client.delete(source_key)
        self._delete_settings_for_source(source)
