#!/usr/bin/env python
"""
Executable for the Ceryx server.
"""

from ceryx import settings
from ceryx.api import app

if __name__ == '__main__':

    app.run(host=settings.API_BIND_HOST, port=settings.API_BIND_PORT, debug=True)

