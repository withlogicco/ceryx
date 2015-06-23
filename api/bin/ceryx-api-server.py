#!/usr/bin/env python
"""
Executable for the Ceryx server.
"""

if __name__ == '__main__':
    from ceryx import settings
    from ceryx.api import app
    app.run(host=settings.API_BIND_HOST, port=settings.API_BIND_PORT)
