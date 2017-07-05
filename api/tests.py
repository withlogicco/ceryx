import unittest

from flask import json

import ceryx

class CeryxTestCase(unittest.TestCase):
    def setUp(self):
        ceryx.api.app.testing = True
        self.app = ceryx.api.app.test_client()

    def test_list_routes(self):
        """
        Assert that listing routes will return a JSON list.
        """
        resp = self.app.get('/api/routes')
        self.assertEqual(resp.status_code, 200)
        type_of_routes = type(json.loads(resp.data))
        self.assertEqual(type_of_routes, list)

    def test_create_route(self):
        """
        Assert that creating a route, will result in the appropriate route.
        """
        route_data = {
            'source': 'test.dev',
            'target': 'localhost:11235'
        }
        
        # Create a route and assert valid data in response
        resp = self.app.post('/api/routes', data=route_data)
        self.assertEqual(resp.status_code, 201)
        self.assertDictEqual(json.loads(resp.data), route_data)
        
        # Also get the route and assert valid data
        resp = self.app.get('/api/routes/test.dev')
        self.assertDictEqual(json.loads(resp.data), route_data)

    def test_delete_route(self):
        """
        Assert that deleting a route, will actually delete it.
        """
        route_data = {
            'source': 'test.dev',
            'target': 'localhost:11235'
        }
        
        # Create a route
        resp = self.app.post('/api/routes', data=route_data)
        
        # Delete the route
        resp = self.app.delete('/api/routes/test.dev')
        self.assertEqual(resp.status_code, 204)
        
        # Also get the route and assert that it does not exist
        resp = self.app.get('/api/routes/test.dev')
        self.assertEqual(resp.status_code, 404)
        


if __name__ == '__main__':
    unittest.main()