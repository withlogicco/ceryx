import unittest

from apistar import test

from app import app


CLIENT = test.TestClient(app)


class CeryxTestCase(unittest.TestCase):
    def setUp(self):
        self.client = CLIENT

    def test_list_routes(self):
        """
        Assert that listing routes will return a JSON list.
        """
        response = self.client.get('/api/routes')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.json()), list)

    def test_create_route_without_protocol(self):
        """
        Assert that creating a route, will result in the appropriate route.
        """
        request_body = {
            'source': 'test.dev',
            'target': 'localhost:11235',
        }
        response_body = {
            'source': 'test.dev',
            'target': 'http://localhost:11235',
            'settings': {
                'enforce_https': False,
                'mode': 'proxy',
            }
        }
        
        # Create a route and assert valid data in response
        response = self.client.post('/api/routes', json=request_body)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(response.json(), response_body)
        
        # Also get the route and assert valid data
        response = self.client.get('/api/routes/test.dev')
        self.assertDictEqual(response.json(), response_body)

    def test_create_route_with_http_protocol(self):
        """
        Assert that creating a route, will result in the appropriate route.
        """
        request_body = {
            'source': 'test.dev',
            'target': 'http://localhost:11235',
        }
        response_body = {
            'source': 'test.dev',
            'target': 'http://localhost:11235',
            'settings': {
                'enforce_https': False,
                'mode': 'proxy',
            }
        }
        
        # Create a route and assert valid data in response
        response = self.client.post('/api/routes', json=request_body)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(response.json(), response_body)
        
        # Also get the route and assert valid data
        response = self.client.get('/api/routes/test.dev')
        self.assertDictEqual(response.json(), response_body)

    def test_create_route_with_https_protocol(self):
        """
        Assert that creating a route, will result in the appropriate route.
        """
        request_body = {
            'source': 'test.dev',
            'target': 'https://localhost:11235',
        }
        response_body = {
            'source': 'test.dev',
            'target': 'https://localhost:11235',
            'settings': {
                'enforce_https': False,
                'mode': 'proxy',
            }
        }
        
        # Create a route and assert valid data in response
        response = self.client.post('/api/routes', json=request_body)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(response.json(), response_body)
        
        # Also get the route and assert valid data
        response = self.client.get('/api/routes/test.dev')
        self.assertDictEqual(response.json(), response_body)

    def test_enforce_https(self):
        """
        Assert that creating a route with the `enforce_https` settings returns
        the expected results
        """
        route_without_enforce_https_request_body = {
            'source': 'test-no-enforce-https.dev',
            'target': 'http://localhost:11235',
        }
        route_enforce_https_true = {
            'source': 'test-enforce-https-true.dev',
            'target': 'http://localhost:11235',
            'settings': {
                'enforce_https': True,
                'mode': 'proxy',
            },
        }
        route_enforce_https_false = {
            'source': 'test-enforce-https-false.dev',
            'target': 'http://localhost:11235',
            'settings': {
                'enforce_https': False,
                'mode': 'proxy',
            },
        }
        route_without_enforce_https_response_body = {
            'source': 'test-no-enforce-https.dev',
            'target': 'http://localhost:11235',
            'settings': {
                'enforce_https': False,
                'mode': 'proxy',
            },
        }
        
        response = self.client.post('/api/routes', json=route_without_enforce_https_request_body)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(
            response.json(), route_without_enforce_https_response_body,
        )
        
        response = self.client.get('/api/routes/test-no-enforce-https.dev')
        self.assertDictEqual(
            response.json(), route_without_enforce_https_response_body,
        )
        
        response = self.client.post('/api/routes', json=route_enforce_https_true)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(
            response.json(), route_enforce_https_true,
        )
        
        response = self.client.get('/api/routes/test-enforce-https-true.dev')
        self.assertDictEqual(
            response.json(), route_enforce_https_true,
        )
        
        response = self.client.post('/api/routes', json=route_enforce_https_false)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(
            response.json(), route_enforce_https_false,
        )
        
        response = self.client.get('/api/routes/test-enforce-https-false.dev')
        self.assertDictEqual(
            response.json(), route_enforce_https_false,
        )

    def test_mode(self):
        """
        Assert that creating a route with or without the `mode` setting returns
        the expected results.
        """
        route_without_mode = {
            'source': 'www.my-website.dev',
            'target': 'http://localhost:11235',
        }
        route_mode_proxy = {
            'source': 'www.my-website.dev',
            'target': 'http://localhost:11235',
            'settings': {
                'enforce_https': False,
                'mode': 'proxy',
            },
        }
        route_mode_redirect = {
            'source': 'my-website.dev',
            'target': 'http://www.my-website.dev',
            'settings': {
                'enforce_https': False,
                'mode': 'redirect',
            },
        }
        
        response = self.client.post('/api/routes', json=route_without_mode)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(
            response.json(), route_mode_proxy,
        )
        
        response = self.client.get('/api/routes/www.my-website.dev')
        self.assertDictEqual(
            response.json(), route_mode_proxy,
        )
        
        response = self.client.post('/api/routes', json=route_mode_proxy)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(
            response.json(), route_mode_proxy,
        )
        
        response = self.client.get('/api/routes/www.my-website.dev')
        self.assertDictEqual(
            response.json(), route_mode_proxy,
        )
        
        response = self.client.post('/api/routes', json=route_mode_redirect)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(
            response.json(), route_mode_redirect,
        )
        
        response = self.client.get('/api/routes/my-website.dev')
        self.assertDictEqual(
            response.json(), route_mode_redirect,
        )

    def test_delete_route(self):
        """
        Assert that deleting a route, will actually delete it.
        """
        route_data = {
            'source': 'test.dev',
            'target': 'http://localhost:11235'
        }
        
        # Create a route
        response = self.client.post('/api/routes', json=route_data)
        
        # Delete the route
        response = self.client.delete('/api/routes/test.dev')
        self.assertEqual(response.status_code, 204)
        
        # Also get the route and assert that it does not exist
        response = self.client.get('/api/routes/test.dev')
        self.assertEqual(response.status_code, 404)
        


if __name__ == '__main__':
    unittest.main()