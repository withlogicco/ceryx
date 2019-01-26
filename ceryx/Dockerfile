FROM openresty/openresty:1.13.6.1-xenial

ARG user=www-data
ARG group=www-data

RUN mkdir -p /etc/letsencrypt &&\
    openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
        -subj '/CN=sni-support-required-for-valid-ssl' \
        -keyout /etc/ssl/resty-auto-ssl-fallback.key \
        -out /etc/ssl/resty-auto-ssl-fallback.crt

# Install dockerize binary, for templated configs
# https://github.com/jwilder/dockerize
ENV DOCKERIZE_VERSION=v0.6.1
RUN curl -fSslL https://github.com/jwilder/dockerize/releases/download/${DOCKERIZE_VERSION}/dockerize-linux-amd64-${DOCKERIZE_VERSION}.tar.gz | \
    tar xzv -C /usr/local/bin/

# Install lua-resty-auto-ssl for dynamically generating certificates from LE
# https://github.com/GUI/lua-resty-auto-ssl
RUN /usr/local/openresty/luajit/bin/luarocks install lua-resty-auto-ssl 0.12.0 &&\
    mkdir /etc/resty-auto-ssl/ &&\
    chown -R $user:$group /etc/resty-auto-ssl/

RUN rm -f /usr/local/openresty/nginx/conf/*

COPY ./nginx/conf /usr/local/openresty/nginx/conf
COPY ./nginx/lualib /usr/local/openresty/nginx/lualib
COPY ./static /etc/ceryx/static

# Add the entrypoint script
COPY ./bin/entrypoint.sh /entrypoint.sh
ENTRYPOINT [ "/entrypoint.sh" ]

CMD ["/usr/local/openresty/bin/openresty", "-g", "daemon off;"]
