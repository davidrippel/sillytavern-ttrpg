#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/solo-ttrpg-assistant"
TARGET_ROOT="${HOME}/Development/SillyTavern/public/scripts/extensions/third-party"
TARGET_DIR="${TARGET_ROOT}/solo-ttrpg-assistant"

if [[ ! -d "${SOURCE_DIR}" ]]; then
    echo "Source extension directory not found: ${SOURCE_DIR}" >&2
    exit 1
fi

if [[ ! -d "${TARGET_ROOT}" ]]; then
    echo "Target SillyTavern extensions directory not found: ${TARGET_ROOT}" >&2
    exit 1
fi

echo "Removing old deployment at ${TARGET_DIR}"
rm -rf "${TARGET_DIR}"

echo "Copying ${SOURCE_DIR} -> ${TARGET_ROOT}"
cp -R "${SOURCE_DIR}" "${TARGET_ROOT}/"

echo "Deployed ${SOURCE_DIR} -> ${TARGET_DIR}"
