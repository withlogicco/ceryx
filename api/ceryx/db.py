"""
Simple Redis client, implemented the data logic of Ceryx.
"""
import redis

from ceryx import settings

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
                           0, settings.REDIS_PREFIX)

    def __init__(self, host, port, db, prefix):
        self.client = redis.StrictRedis(host=host, port=port, db=db)
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
            return target_host

    def lookup_hosts(self, pattern):
        """
        Fetches hosts that match the given pattern. If no pattern is given,
        all hosts are returned.
        """
        if not pattern:
            pattern = '*'
        lookup_pattern = self._prefixed_route_key(pattern)
        keys = self.client.keys(lookup_pattern)
        return [key[len(lookup_pattern) - len(pattern):] for key in keys]

    def lookup_routes(self, pattern):
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
                    'target': self.lookup(host, silent=True)
                }
            )
        return routes

    def insert(self, source, target):
        """
        Inserts a new source/target host entry in to the database.
        """
        source_key = self._prefixed_route_key(source)
        self.client.set(source_key, target)

    def delete(self, source):
        """
        Deletes the entry of the given source, if it exists.
        """
        source_key = self._prefixed_route_key(source)
        self.client.delete(source_key)
