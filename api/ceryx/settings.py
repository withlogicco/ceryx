"""
Settings file, which is populated from the environment while enforcing common
use-case defaults.
"""
import os


DEBUG = True
if os.getenv("CERYX_DEBUG", "").lower() in ["0", "no", "false"]:
    DEBUG = False

API_BIND_HOST = os.getenv("CERYX_API_HOST", "127.0.0.1")
API_BIND_PORT = int(os.getenv("CERYX_API_PORT", 5555))
SECRET_KEY = os.getenv("CERYX_SECRET_KEY")
if SECRET_KEY:
    with open(SECRET_KEY, "r") as f:
        SECRET_KEY = f.read()

REDIS_HOST = os.getenv("CERYX_REDIS_HOST", None)
print("REDIS_HOST ----->")
print(REDIS_HOST)
REDIS_PORT = int(os.getenv("CERYX_REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("CERYX_REDIS_PASSWORD", None)
REDIS_PREFIX = os.getenv("CERYX_REDIS_PREFIX", "ceryx")
REDIS_TIMEOUT = int(os.getenv("CERYX_REDIS_TIMEOUT", 100)) * 0.001 # Python Redis client requires units of seconds
