"""
Package containig the classes related to the API of Ceryx.
"""
from flask import Flask
from flask.ext import restful
from ceryx.api.views import Route
from ceryx.api.views import RoutesList


app = Flask('ceryx-api')
app.config.from_object('ceryx.settings')
api = restful.Api(app)

api.add_resource(RoutesList, '/api/routes', '/route/', '/route')
api.add_resource(Route, '/api/routes/<string:source>')
