FROM python:3.6

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install pipenv==2018.11.26

WORKDIR /usr/src/app

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --dev --deploy

COPY . ./

ENV CERYX_DEBUG true
ENV CERYX_DISABLE_LETS_ENCRYPT true

COPY --from=sourcelair/ceryx:latest /etc/ceryx/ssl/default.key /etc/ceryx/ssl/default.key
COPY --from=sourcelair/ceryx:latest /etc/ceryx/ssl/default.crt /etc/ceryx/ssl/default.crt

CMD ["pytest", "tests/"]