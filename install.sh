#!/usr/bin/env bash
set -euo pipefail

# Prefixr one-liner installer — pipx-managed, no repo clone required
# Usage: curl -fsSL prefixr.dev/install | bash

PREFIXR_VERSION="${PREFIXR_VERSION:-}"
PIPX_BIN="${PIPX_BIN:-pipx}"

echo "Installing Prefixr…"

if ! command -v "$PIPX_BIN" &>/dev/null; then
  echo "pipx not found. Installing pipx…"
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  export PATH="$HOME/.local/bin:$PATH"
fi

if [ -n "$PREFIXR_VERSION" ]; then
  "$PIPX_BIN" install "prefixr==${PREFIXR_VERSION}" --force
else
  "$PIPX_BIN" install prefixr --force
fi

echo ""
echo "Prefixr installed."
echo ""
echo "  prefixr init    # configure API keys"
echo "  prefixr run     # start proxy + dashboard"
echo ""
echo "Dashboard: http://localhost:4242/dashboard"
echo "Proxy:     http://localhost:4242/v1/chat/completions"
