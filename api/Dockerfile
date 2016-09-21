FROM python:2.7.11-alpine
MAINTAINER Antonis Kalipetis <akalipetis@gmail.com>

COPY . /opt/ceryx
WORKDIR /opt/ceryx
RUN pip install /opt/ceryx 
CMD ceryx-api-server.py
