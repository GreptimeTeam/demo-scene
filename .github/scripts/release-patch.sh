#!/usr/bin/env bash
# Bump the GreptimeDB release used by every demo, e.g. `release-patch.sh 1.3.2`.
set -euo pipefail

VERSION=${1:?usage: release-patch.sh <major.minor.patch>}
if [[ ! $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Expected a stable release such as 1.3.2, got '$VERSION'" >&2
  exit 1
fi
TAG="v$VERSION"
cd "$(git rev-parse --show-toplevel)"

# Fails while the image is not published yet. The OpenTelemetry playground pins the multi-arch index digest.
DIGEST=$(curl -fsS "https://hub.docker.com/v2/repositories/greptime/greptimedb/tags/$TAG" | jq -er .digest)

git grep -lz 'greptime/greptimedb:v' -- ':!.github' |
  xargs -0 perl -pi -e "s#greptime/greptimedb:v[\\w.-]+#greptime/greptimedb:$TAG#g"
perl -pi -e "s#greptime/greptimedb\\@sha256:[0-9a-f]{64}#greptime/greptimedb\\@$DIGEST#" \
  opentelemetry-playground/images.lock.json
perl -pi -e "s#(Docker-based demos use GreptimeDB )v[\\w.-]+#\${1}$TAG#" README.md

# The lock file and README are matched by wording; fail instead of opening a partial PR when it changes.
grep -q "greptime/greptimedb@$DIGEST" opentelemetry-playground/images.lock.json
grep -q "Docker-based demos use GreptimeDB $TAG " README.md
