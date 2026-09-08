#!/usr/bin/env bash
set -euo pipefail

proxy_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a
# shellcheck disable=SC1091
. "$proxy_dir/runtime.env"
set +a
cd "$proxy_dir/.."
exec python3 -m proxy.server
