from setuptools import setup

setup(
    name='ceryx',
    version='0.2.0',
    author='Antonis Kalipetis, SourceLair PC',
    author_email=('Antonis Kalipetis <akalipetis@gmail.com>, '
                  'SourceLair PC <support@sourcelair.com>'),
    packages=['ceryx', 'ceryx.api'],
    scripts=['bin/ceryx-api-server.py', ],
    url='https://pypi.python.org/sourcelair/ceryx/',
    license=open('LICENSE.txt').read(),
    description='Ceryx, a dynamic reverse proxy based on NGINX OpenResty.',
    long_description=open('README.md').read(),
    install_requires=[
        'redis==2.10.3',
        'Flask==0.10.1',
        'Flask-RESTful==0.2.12',
    ],
)

from distutils.core import setup
