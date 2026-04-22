# workerd ships glibc binaries, so alpine/musl can fail at runtime.
FROM node:22-slim

# workerd's BoringSSL doesn't auto-discover Debian's CA bundle —
# without this, outbound HTTPS fails with "unable to get local issuer".
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund --loglevel=error

COPY src ./src
COPY wrangler.toml tsconfig.json ./

EXPOSE 8787

# --ip 0.0.0.0 so the published port reaches the host.
CMD ["npx", "wrangler", "dev", "--ip", "0.0.0.0", "--port", "8787"]
