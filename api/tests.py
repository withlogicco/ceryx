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
        response = self.client.get('/api/routes/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(type(response.json()), list)

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
        response = self.client.post('/api/routes/', json=route_data)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(response.json(), expected_response)
        
        # Also get the route and assert valid data
        response = self.client.get('/api/routes/test.dev/')
        self.assertDictEqual(response.json(), expected_response)

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
        
        response = self.client.post('/api/routes/', json=route_without_enforce_https)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(
            response.json(), expected_response_without_enforce_https,
        )
        
        response = self.client.get('/api/routes/test-no-enforce-https.dev/')
        self.assertDictEqual(
            response.json(), expected_response_without_enforce_https,
        )
        
        response = self.client.post('/api/routes/', json=route_enforce_https_true)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(
            response.json(), route_enforce_https_true,
        )
        
        response = self.client.get('/api/routes/test-enforce-https-true.dev/')
        self.assertDictEqual(
            response.json(), route_enforce_https_true,
        )
        
        response = self.client.post('/api/routes/', json=route_enforce_https_false)
        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(
            response.json(), route_enforce_https_false,
        )
        
        response = self.client.get('/api/routes/test-enforce-https-false.dev/')
        self.assertDictEqual(
            response.json(), route_enforce_https_false,
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
        response = self.client.post('/api/routes/', json=route_data)
        
        # Delete the route
        response = self.client.delete('/api/routes/test.dev/')
        self.assertEqual(response.status_code, 204)
        
        # Also get the route and assert that it does not exist
        response = self.client.get('/api/routes/test.dev/')
        self.assertEqual(response.status_code, 404)
        


if __name__ == '__main__':
    unittest.main()