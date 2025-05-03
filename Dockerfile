FROM python:3.13-alpine

RUN pip --no-cache-dir --disable-pip-version-check --no-input -q install rns

RUN mkdir /config

RUN addgroup -S rns --gid 1000 && adduser -S rns --uid 1000 -G rns
RUN chown rns:rns /config

USER rns:rns
                                                                                                              
VOLUME ["/config"]

ENTRYPOINT ["/usr/local/bin/rnsd", "--config", "/config"]
