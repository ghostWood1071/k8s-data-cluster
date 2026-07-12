#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-ghostwood/airflow}"
IMAGE_TAG="${IMAGE_TAG:-2.10.3-dbdag}"

cd "$SCRIPT_DIR"

docker build \
  -t "${IMAGE_REPOSITORY}:${IMAGE_TAG}" \
  .

echo "Built ${IMAGE_REPOSITORY}:${IMAGE_TAG}"
