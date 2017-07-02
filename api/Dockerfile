FROM python:2.7.11
MAINTAINER Antonis Kalipetis <akalipetis@gmail.com>

COPY . /opt/ceryx
WORKDIR /opt/ceryx

RUN pip install /opt/ceryx

CMD python bin/ceryx-api-server.py
