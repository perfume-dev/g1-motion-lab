#!/usr/bin/env bash
# Copyright (c) 2026 Daito Manabe. MIT; build tooling only.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
of_root="${1:-${OF_ROOT:-}}"
jobs="${JOBS:-2}"
if [[ $# -gt 1 || -z "$of_root" ]]; then
	echo "usage: $0 /path/to/openFrameworks-0.12.1" >&2
	exit 2
fi
if [[ ! "$jobs" =~ ^[1-9][0-9]*$ ]]; then
	echo "JOBS must be a positive integer." >&2
	exit 2
fi
if [[ ! -f "$of_root/libs/openFrameworksCompiled/project/makefileCommon/compile.project.mk" ]]; then
	echo "Not an openFrameworks root: $of_root" >&2
	exit 2
fi
of_root="$(cd "$of_root" && pwd)"

# Stage the canonical package without overwriting user-edited staged assets.
python3 "$repo_root/scripts/prepare-data.py" --viewer openframeworks
make -C "$repo_root/examples/openframeworks" Release OF_ROOT="$of_root" -j"$jobs"
