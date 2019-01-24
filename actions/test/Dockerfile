FROM ubuntu:18.04

LABEL "com.github.actions.name"="Ceryx Test"
LABEL "com.github.actions.description"="Ensure that Ceryx routes requests as expected."

LABEL "repository"="http://github.com/sourcelair/ceryx"
LABEL "maintainer"="Paris Kasidiaris <paris@sourcelair.com>"

WORKDIR /usr/src/app


RUN apt-get update && \
    apt-get install -y curl httpie

ARG docker_version=18.09.1
RUN curl -sSL https://download.docker.com/linux/static/stable/x86_64/docker-${docker_version}.tgz | tar -xz && \
    mv docker/docker /usr/local/bin/docker && \
    rm -rf docker

ARG bats_version=1.1.0
RUN curl -sSL https://github.com/bats-core/bats-core/archive/v${bats_version}.tar.gz | tar -xz && \
    ./bats-core-${bats_version}/install.sh /usr/local && \
    rm -rf ./bats-core-${bats_version}

COPY .env.test /etc/ceryx/.env.test

ARG entrypoint_path=/usr/local/bin/entrypoint
COPY entrypoint $entrypoint_path
ENTRYPOINT ["entrypoint"]