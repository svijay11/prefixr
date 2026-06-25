#!/usr/bin/env bash
set -euo pipefail

# Prefixr installer — installs directly from GitHub
# Usage: curl -fsSL https://raw.githubusercontent.com/svijay11/prefixr/main/install.sh | bash

REPO="${PREFIXR_REPO:-git+https://github.com/svijay11/prefixr.git}"
PIPX_BIN="${PIPX_BIN:-pipx}"

echo "Installing Prefixr from GitHub…"

if command -v "$PIPX_BIN" &>/dev/null; then
  "$PIPX_BIN" install "$REPO" --force
else
  echo "pipx not found — installing with pip…"
  python3 -m pip install --user "$REPO"
  echo ""
  echo "If 'prefixr' is not found, add pip's bin dir to PATH:"
  echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "Prefixr installed."
echo ""
echo "  prefixr init    # configure API keys"
echo "  prefixr run     # start proxy + dashboard"
echo ""
echo "Dashboard: http://localhost:4242/dashboard"
echo "Proxy:     http://localhost:4242/v1/chat/completions"
