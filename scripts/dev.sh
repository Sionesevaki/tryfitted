#!/usr/bin/env bash
set -euo pipefail

docker compose -f infra/docker-compose.yml up -d

echo "Starting API..."
pnpm --filter @tryfitted/api dev

