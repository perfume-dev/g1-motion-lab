#!/usr/bin/env bash
# Copyright (c) 2026 Daito Manabe. SPDX-License-Identifier: MIT
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
viewer_python="${G1_PYTHON:-${repo_root}/examples/python/.venv/bin/python}"
artifact_dir="${1:-${repo_root}/artifacts/python}"
if [[ ! -x "$viewer_python" ]]; then
  echo "Python environment missing. Run: uv sync --frozen --project examples/python --python 3.12" >&2
  exit 1
fi
cd "$repo_root"
"$viewer_python" -W error -m unittest discover -s tests/python -p 'test_*.py' -v
"$viewer_python" tests/python/check_runtime.py "$artifact_dir"
