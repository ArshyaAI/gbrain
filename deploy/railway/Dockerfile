FROM debian:bookworm-slim
ARG GBRAIN_VERSION=0.60.243.0
ARG GBRAIN_SHA256=687f3c1f142eaef66a4387699f09ceedead122677b714774bceef12ed747cf4a
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl tini git \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL --retry 3 "https://github.com/garrytan/gbrain/releases/download/v${GBRAIN_VERSION}/gbrain-linux-x64" -o /usr/local/bin/gbrain \
    && echo "${GBRAIN_SHA256}  /usr/local/bin/gbrain" | sha256sum -c - \
    && chmod 755 /usr/local/bin/gbrain \
    && gbrain --version
WORKDIR /opt/gbrain
COPY skills/ ./skills/
COPY deploy/railway/entrypoint.sh /usr/local/bin/gbrain-entrypoint
RUN chmod 755 /usr/local/bin/gbrain-entrypoint
ENV GBRAIN_HOME=/data GBRAIN_NO_AUTOPILOT_INSTALL=1 GBRAIN_MODEL_DISCOVERY=0 GBRAIN_SWEEP=0
EXPOSE 3131
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/gbrain-entrypoint"]
