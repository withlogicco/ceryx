FROM openresty/openresty:1.13.6.1-xenial

COPY ./nginx/conf /usr/local/openresty/nginx/conf
COPY ./nginx/lualib /usr/local/openresty/nginx/lualib
COPY ./nginx/sites-enabled /usr/local/openresty/nginx/sites-enabled

RUN mkdir -p /etc/letsencrypt &&\
    openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
        -subj '/CN=sni-support-required-for-valid-ssl' \
        -keyout /etc/ssl/resty-auto-ssl-fallback.key \
        -out /etc/ssl/resty-auto-ssl-fallback.crt

RUN /usr/local/openresty/luajit/bin/luarocks install lua-resty-auto-ssl 0.11.1
