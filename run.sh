#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
PYTHON=python3
if [[ -x .venv/bin/python ]]; then
  PYTHON=.venv/bin/python
fi
if [[ $# -eq 0 ]]; then
  exec "$PYTHON" -m blockblast.desktop
fi
exec "$PYTHON" -m blockblast "$@"
