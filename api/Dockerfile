FROM python:3.6

RUN pip install pipenv==11.9.0

RUN mkdir /etc/ceryx
COPY Pipfile Pipfile.lock /etc/ceryx/

WORKDIR  /etc/ceryx
RUN pipenv install --system --dev --deploy

COPY . /opt/ceryx
WORKDIR /opt/ceryx

ENV PORT 5555
CMD python api.py
