FROM debian:jessie
MAINTAINER Antonis Kalipetis <akalipetis@gmail.com>

RUN apt-get update -y
RUN apt-get install -y python-dev python-pip git

ADD . /ceryx
WORKDIR /ceryx

RUN python setup.py develop

EXPOSE 5555

CMD ceryx-api-server.py