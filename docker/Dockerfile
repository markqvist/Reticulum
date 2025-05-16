ARG python_version=3.13

FROM python:${python_version}-alpine AS build

#RUN apk add --no-cache build-base linux-headers libffi-dev libressl-dev cargo

ENV PIP_ROOT_USER_ACTION=ignore
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
RUN pip install rns

#FROM python:${python_version}-alpine
#ARG python_version

# Only copy the necessary files from the build stage, to improve layer efficiency
#COPY --from=build /usr/local/bin/rn* /usr/local/bin/
#COPY --from=build /usr/local/lib/python${python_version}/site-packages/ /usr/local/lib/python${python_version}/site-packages/

RUN mkdir /config

RUN addgroup -S rns --gid 1000 && adduser -S rns --uid 1000 -G rns
RUN chown rns:rns /config

USER rns:rns

VOLUME ["/config"]

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/usr/local/bin/rnsd", "--config", "/config"]
