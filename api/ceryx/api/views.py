from __future__ import absolute_import

from flask import request 
from flask.ext.restful import reqparse, abort, Resource, fields, marshal_with

from ceryx.db import RedisRouter


settings_fields = {
    'enforce_https': fields.Boolean(default=False),
}
resource_fields = {
    'source': fields.String,
    'target': fields.String,
    'settings': fields.Nested(settings_fields),
}

parser = reqparse.RequestParser()
parser.add_argument(
    'source', type=str, required=True, help='Source is required'
)
parser.add_argument(
    'target', type=str, required=True, help='Target is required'
)
parser.add_argument(
    'settings', type=dict,
)

update_parser = reqparse.RequestParser()
update_parser.add_argument(
    'target', type=str, required=True, help='Target is required'
)
update_parser.add_argument(
    'settings', type=dict,
)

router = RedisRouter.from_config()


def lookup_or_abort(source):
    """
    Returns the target for the given source, or aborts raising a 404
    """
    try:
        resource = {
            'source': source,
            'target': router.lookup(source),
            'settings': router.lookup_settings(source),
        }
        return resource
    except RedisRouter.LookupNotFound:
        abort(
            404, message='Route with source {} doesn\'t exist'.format(source)
        )


class Route(Resource):
    """
    Resource describing a single Route. Supports GET, DELETE and PUT. The
    format is the following:
    ```
    {
        "source": "[source]",
        "target": "[target]"
    }
    ```
    """

    @marshal_with(resource_fields)
    def get(self, source):
        """
        Fetches the route with the given source
        """
        route = lookup_or_abort(source)
        return route

    @marshal_with(resource_fields)
    def delete(self, source):
        """
        Deletes the route with the given source
        """
        route = lookup_or_abort(source)
        router.delete(source)
        return route, 204

    @marshal_with(resource_fields)
    def put(self, source):
        """
        Creates or updates the route with the given source, pointing to the
        given target
        """
        args = update_parser.parse_args()
        args['settings']['enforce_https'] = (
            1 if args['settings']['enforce_https'] else 0
        )
        router.insert(source, **args)
        return args, 201


class RoutesList(Resource):
    """
    Backwards compatible API route, which is used to create or udpate a source
    to point to the given target.
    """

    @marshal_with(resource_fields)
    def post(self):
        """
        Creates or updates the route with the given source, pointing to the
        given target
        """
        args = parser.parse_args()
        router.insert(**args)
        return args, 201

    @marshal_with(resource_fields)
    def get(self):
        """
        Fetches all the routes from the database, optionally using a "pattern"
        GET parameter to filter them first.
        """
        pattern = request.args.get('pattern')
        routes = router.lookup_routes(pattern)
        return routes
