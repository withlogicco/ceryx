"""
Settings file, which is populated from the environment while enforcing common
use-case defaults.
"""
import os

NAME = os.getenv('CERYX_NAME', 'ceryx')
DEBUG = True
if os.getenv('CERYX_DEBUG', '').lower() in ['0', 'no', 'false']:
    DEBUG = False

API_BIND_HOST = os.getenv('CERYX_API_HOST', '127.0.0.1')
API_BIND_PORT = int(os.getenv('CERYX_API_PORT', 5555))
SERVER_NAME = os.getenv('CERYX_SERVER_NAME')
SECRET_KEY = os.getenv('CERYX_SECRET_KEY')
if SECRET_KEY:
    with open(SECRET_KEY, 'r') as f:
        SECRET_KEY = f.read()

REDIS_HOST = os.getenv('CERYX_REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('CERYX_REDIS_PORT', 6379))
REDIS_PREFIX = os.getenv('CERYX_REDIS_PREFIX', 'ceryx')
