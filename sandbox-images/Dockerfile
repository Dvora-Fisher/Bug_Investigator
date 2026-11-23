# One sandbox image definition for every runtime. The builder passes the base image and an
# optional setup command per runtime (see backend/src/investigator/runtimes/adapters.py).
ARG BASE_IMAGE=debian:bookworm-slim
FROM ${BASE_IMAGE}

ARG SETUP="true"

# Extra trusted root certificates from the host (for example a filtering proxy such as NetFree).
# The folder may be empty. Without this, package downloads fail behind HTTPS-inspecting proxies.
COPY certs/ /usr/local/share/ca-certificates/host/
RUN (command -v update-ca-certificates >/dev/null 2>&1 \
      || (apt-get update && apt-get install -y --no-install-recommends ca-certificates \
          && rm -rf /var/lib/apt/lists/*)) \
    && update-ca-certificates

ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt \
    HOME=/tmp \
    CI=true \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1

RUN sh -c "$SETUP"

# Project code never runs as root.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin runner
USER 10001:10001
WORKDIR /workspace
