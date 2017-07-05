from setuptools import setup


with open('requirements.txt') as requirements_file:
    requirements = [line.strip() for line in requirements_file.readlines()]
    
    
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
    install_requires=requirements,
)

from distutils.core import setup
