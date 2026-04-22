# node:22-slim (Debian-based, glibc) — workerd ships glibc binaries, so
# alpine/musl can fail at runtime. slim is a good size/compat balance.
FROM node:22-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund --loglevel=error

# Copy source. Keep this minimal — anything not needed at runtime is in
# .dockerignore.
COPY src ./src
COPY wrangler.toml tsconfig.json ./

EXPOSE 8787

# `wrangler dev` defaults to local mode (workerd in-process). The
# `--ip 0.0.0.0` override is required inside a container so the published
# port reaches the host.
CMD ["npx", "wrangler", "dev", "--ip", "0.0.0.0", "--port", "8787"]
