FROM python:2.7.11
MAINTAINER Antonis Kalipetis <akalipetis@gmail.com>

ARG PIP_REQUIREMENTS_FILE=requirements.txt

COPY . /opt/ceryx
WORKDIR /opt/ceryx

RUN pip install -r $PIP_REQUIREMENTS_FILE

CMD python server.py
