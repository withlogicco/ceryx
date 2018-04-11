import json
import unittest

from flask import json

import ceryx

class CeryxTestingClientProxy(object):
    def __init__(self, upstream_client):
        self._upstream = upstream_client
    
    def _request(self, method, path, data=None):
        _method = getattr(self._upstream, method)
        json_data = json.dumps(data) if data else None
        return _method(path, data=json_data, content_type='application/json')

    def get(self, path):
        return self._request('get', path)
    
    def post(self, path, data):
        return self._request('post', path, data=data)
    
    def delete(self, path):
        return self._request('delete', path)


class CeryxTestCase(unittest.TestCase):
    def setUp(self):
        ceryx.api.app.testing = True
        testing_client = ceryx.api.app.test_client()
        self.app = CeryxTestingClientProxy(testing_client)

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
            'target': 'localhost:11235',
        }
        expected_response = {
            'source': 'test.dev',
            'target': 'localhost:11235',
            'settings': {
                'enforce_https': False,
            }
        }
        
        # Create a route and assert valid data in response
        resp = self.app.post('/api/routes', data=route_data)
        self.assertEqual(resp.status_code, 201)
        self.assertDictEqual(json.loads(resp.data), expected_response)
        
        # Also get the route and assert valid data
        resp = self.app.get('/api/routes/test.dev')
        self.assertDictEqual(json.loads(resp.data), expected_response)

    def test_enforce_https(self):
        """
        Assert that creating a route with the `enforce_https` settings returns
        the expected results
        """
        route_without_enforce_https = {
            'source': 'test-no-enforce-https.dev',
            'target': 'localhost:11235',
        }
        route_enforce_https_true = {
            'source': 'test-enforce-https-true.dev',
            'target': 'localhost:11235',
            'settings': {
                'enforce_https': True,
            },
        }
        route_enforce_https_false = {
            'source': 'test-enforce-https-false.dev',
            'target': 'localhost:11235',
            'settings': {
                'enforce_https': False,
            },
        }
        expected_response_without_enforce_https = {
            'source': 'test-no-enforce-https.dev',
            'target': 'localhost:11235',
            'settings': {
                'enforce_https': False,
            },
        }
        
        resp = self.app.post('/api/routes', data=route_without_enforce_https)
        self.assertEqual(resp.status_code, 201)
        self.assertDictEqual(
            json.loads(resp.data), expected_response_without_enforce_https,
        )
        
        resp = self.app.get('/api/routes/test-no-enforce-https.dev')
        self.assertDictEqual(
            json.loads(resp.data), expected_response_without_enforce_https,
        )
        
        resp = self.app.post('/api/routes', data=route_enforce_https_true)
        self.assertEqual(resp.status_code, 201)
        self.assertDictEqual(
            json.loads(resp.data), route_enforce_https_true,
        )
        
        resp = self.app.get('/api/routes/test-enforce-https-true.dev')
        self.assertDictEqual(
            json.loads(resp.data), route_enforce_https_true,
        )
        
        resp = self.app.post('/api/routes', data=route_enforce_https_false)
        self.assertEqual(resp.status_code, 201)
        self.assertDictEqual(
            json.loads(resp.data), route_enforce_https_false,
        )
        
        resp = self.app.get('/api/routes/test-enforce-https-false.dev')
        self.assertDictEqual(
            json.loads(resp.data), route_enforce_https_false,
        )

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