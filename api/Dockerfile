FROM python:3.7

RUN pip install pipenv==2018.11.26

RUN mkdir /etc/ceryx
COPY Pipfile Pipfile.lock /etc/ceryx/

WORKDIR  /etc/ceryx
RUN pipenv install --system --dev --deploy

COPY . /opt/ceryx
WORKDIR /opt/ceryx

ENV PORT 5555
CMD python api.py
