FROM ghcr.io/gitroomhq/postiz-app@sha256:007cebec671144afe6f2d7ba57ec2e96db7c0e58d4513d2072d5ca5f0eaade32

WORKDIR /app

ENV POSTIZ_NODE_OPTIONS=--max-old-space-size=512

COPY docker/provider-healthcheck.mjs /usr/local/bin/provider-healthcheck.mjs
COPY docker/postiz/start-postiz.sh /usr/local/bin/start-postiz.sh

RUN chmod +x /usr/local/bin/start-postiz.sh

CMD ["sh", "-lc", "/usr/local/bin/start-postiz.sh"]
