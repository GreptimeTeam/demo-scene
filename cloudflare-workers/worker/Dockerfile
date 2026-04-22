# node:22-slim (Debian-based, glibc) — workerd ships glibc binaries, so
# alpine/musl can fail at runtime. slim is a good size/compat balance.
FROM node:22-slim

# workerd uses BoringSSL and does not auto-discover Debian's CA bundle.
# Without this, outbound HTTPS from the Worker fails with "unable to get
# local issuer certificate". ca-certificates is already installed by the
# base image; we just need to point workerd at it.
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

# Install dependencies first for better layer caching. package-lock.json
# is committed for reproducible builds, so this works on both BuildKit
# and the legacy docker builder.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund --loglevel=error

# Copy source. Keep this minimal — anything not needed at runtime is in
# .dockerignore.
COPY src ./src
COPY wrangler.toml tsconfig.json ./

EXPOSE 8787

# `wrangler dev` defaults to local mode (workerd in-process). The
# `--ip 0.0.0.0` override is required inside a container so the published
# port reaches the host.
CMD ["npx", "wrangler", "dev", "--ip", "0.0.0.0", "--port", "8787"]
