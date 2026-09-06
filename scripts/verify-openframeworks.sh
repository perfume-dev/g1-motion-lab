#!/usr/bin/env bash
# Copyright (c) 2026 Daito Manabe. MIT; verification tooling only.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
capture_dir="${1:-}"
mode="${2:-all}"
if [[ -z "$capture_dir" || $# -gt 2 || ( "$mode" != all && "$mode" != --negatives-only ) ]]; then
	echo "usage: $0 /path/to/capture-directory [--negatives-only]" >&2
	exit 2
fi
mkdir -p "$capture_dir"
capture_dir="$(cd "$capture_dir" && pwd)"
app="example-g1-motion-lab"
app_bin="$repo_root/examples/openframeworks/bin"

render_app() {
	local artifact="$1"
	shift
	local binary app_pid watchdog_pid result
	case "$(uname -s)" in
		Darwin) binary="$app_bin/$app.app/Contents/MacOS/$app" ;;
		Linux) binary="$app_bin/$app" ;;
		*) echo "Unsupported platform: $(uname -s)" >&2; exit 2 ;;
	esac
	if [[ ! -x "$binary" ]]; then
		echo "Build G1 first with scripts/build-openframeworks.sh." >&2
		exit 1
	fi
	echo "Rendering $artifact (timeout 240s)"
	(
		cd "$app_bin"
		exec "$binary" --smoke-test "--capture=$capture_dir/$artifact.png" "$@"
	) >"$capture_dir/$artifact.log" 2>&1 &
	app_pid=$!
	# 960 G1 frames take over 90 seconds on hosted Mesa; keep the measured
	# 240-second allowance and all acceptance criteria, not an unbounded wait.
	(
		sleep 240
		kill -TERM "$app_pid" 2>/dev/null || true
	) &
	watchdog_pid=$!
	result=0
	wait "$app_pid" || result=$?
	kill "$watchdog_pid" 2>/dev/null || true
	wait "$watchdog_pid" 2>/dev/null || true
	if [[ "$result" -ne 0 ]] || ! grep -q 'SMOKE_TEST_OK' "$capture_dir/$artifact.log" \
		|| [[ ! -s "$capture_dir/$artifact.png" ]]; then
		cat "$capture_dir/$artifact.log" >&2
		echo "$app rendering failed (exit $result)." >&2
		exit 1
	fi
	grep 'SMOKE_TEST_OK' "$capture_dir/$artifact.log"
}

if [[ "$mode" != --negatives-only ]]; then
	# About 8 / 16 seconds. JSON source FPS remains independent of the 60 Hz display clock.
	render_app "$app" --capture-frame=480
	render_app "$app-later" --capture-frame=960
	if cmp -s "$capture_dir/$app.png" "$capture_dir/$app-later.png"; then
		echo "G1 produced identical captures at different motion frames." >&2
		exit 1
	fi
	render_app "$app-source-overlay" --clip=A --source-overlay --capture-frame=960
	render_app "$app-source-hard" --clip=A --source-overlay --capture-frame=860
fi

# These are rendering/input-validation checks, not acceptance of a retarget or
# physical policy. A real export with pose_status=fail may render successfully;
# the application keeps its diagnostic-only and physics-not-validated warnings.
echo "G1 graphics/input checks only: pose QA and physics acceptance are separate."
if ! command -v python3 >/dev/null 2>&1; then
	echo "Python 3 is required for the G1 JSON negative tests (standard library only)." >&2
	exit 1
fi

python3 - "$repo_root" "$capture_dir" <<'PY'
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

repo = Path(sys.argv[1])
capture_dir = Path(sys.argv[2])
app = "example-g1-motion-lab"
source_bin = repo / "examples" / "openframeworks" / "bin"
system = platform.system()
if system == "Darwin":
    executable = Path(f"{app}.app/Contents/MacOS/{app}")
elif system == "Linux":
    executable = Path(app)
else:
    raise SystemExit(f"Unsupported platform: {system}")
if not (source_bin / executable).is_file():
    raise SystemExit("Build G1 first with scripts/build-openframeworks.sh.")

# Copy the entire bin layout, not just the executable: on macOS openFrameworks
# resolves data from the app-bundle location. No negative case can edit originals.
with tempfile.TemporaryDirectory(prefix="of-g1-negatives-") as temporary:
    fixture_bin = Path(temporary) / "bin"
    # Dereference development symlinks so every fixture asset is an owned copy,
    # including a symlinked data or shaders directory.
    shutil.copytree(source_bin, fixture_bin, symlinks=False)
    fixture_data = fixture_bin / "data"
    originals = {
        name: (source_bin / "data" / name).read_bytes()
        for name in ("g1-motion.json", "g1-model.json", "shaders/surface.vert", "shaders/surface.frag")
    }
    cases = (
        ("missing-motion", "Missing bin/data/g1-motion.json"),
        ("missing-model", "Missing bin/data/g1-model.json"),
        ("missing-shader", "G1 surface shaders failed to compile/link"),
        ("invalid-shader", "G1 surface shaders failed to compile/link"),
        ("malformed-json", "JSON object|parse_error|parse error"),
        ("fps-string", "Expected a numeric value"),
        ("fps-zero", "Reference FPS is invalid"),
        ("schema-float", "schema_version must be an integer"),
        ("body-parent-float", "Robot parent must be an integer"),
        ("source-parent-float", "Source parent must be an integer"),
        ("mesh-body-float", "Mesh body index must be an integer"),
        ("mesh-body-overflow", "Mesh body index is out of range"),
        ("mesh-index-float", "Mesh triangle index must be an integer"),
        ("nonunit-quaternion", "Quaternion is not unit length"),
        ("missing-body-offsets", "Missing body_offsets"),
        ("body-offset-count", "Body offset count does not match"),
        ("body-offset-dimensions", "Body offset must contain exactly three numbers"),
        ("body-offset-string", "Expected a numeric value"),
        ("body-offset-overflow", "Non-finite number in G1 data"),
        ("body-offset-inconsistent", "Body offset disagrees with exported world poses"),
        ("root-not-first", "Robot root must be body index 0"),
        ("body-not-parent-first", "Robot hierarchy must be parent-first"),
    )
    results = []
    for name, expected in cases:
        # Restore only disposable files between cases.
        for relative, contents in originals.items():
            path = fixture_data / relative
            if path.is_symlink():
                path.unlink()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
        motion_path = fixture_data / "g1-motion.json"
        model_path = fixture_data / "g1-model.json"
        if name == "missing-motion":
            motion_path.unlink()
        elif name == "missing-model":
            model_path.unlink()
        elif name == "missing-shader":
            (fixture_data / "shaders/surface.vert").unlink()
        elif name == "invalid-shader":
            (fixture_data / "shaders/surface.vert").write_text(
                "#version 150\nTHIS_IS_AN_INTENTIONALLY_INVALID_SHADER\n", encoding="utf-8")
        elif name == "malformed-json":
            motion_path.write_text("{", encoding="utf-8")
        else:
            path = model_path if name.startswith("mesh-") else motion_path
            data = json.loads(path.read_text(encoding="utf-8"))
            if name == "fps-string":
                data["fps"] = "40"
            elif name == "fps-zero":
                data["fps"] = 0
            elif name == "schema-float":
                data["schema_version"] = 1.0
            elif name == "body-parent-float":
                data["body_parents"][1] = 0.5
            elif name == "source-parent-float":
                data["source_parents"][1] = 0.5
            elif name == "mesh-body-float":
                data["meshes"][0]["body"] = 0.5
            elif name == "mesh-body-overflow":
                data["meshes"][0]["body"] = 4294967296
            elif name == "mesh-index-float":
                data["meshes"][0]["indices"][0] = 0.5
            elif name == "nonunit-quaternion":
                data["clips"][0]["frames"][0]["rotations"][:4] = [0, 0, 0, 0]
            elif name == "missing-body-offsets":
                del data["body_offsets"]
            elif name == "body-offset-count":
                data["body_offsets"].pop()
            elif name == "body-offset-dimensions":
                data["body_offsets"][1] = [0, 0]
            elif name == "body-offset-string":
                data["body_offsets"][1][0] = "0"
            elif name == "body-offset-overflow":
                data["body_offsets"][1][0] = 1e39
            elif name == "body-offset-inconsistent":
                data["body_offsets"][1][0] += 0.01
            elif name == "root-not-first":
                data["body_parents"][0] = 1
                data["body_parents"][1] = -1
            elif name == "body-not-parent-first":
                data["body_parents"][1] = 2
                data["body_parents"][2] = 0
            else:
                raise AssertionError(name)
            path.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False), encoding="utf-8")
        artifact = capture_dir / f"{app}-negative-{name}"
        capture_path = artifact.with_suffix(".png")
        if capture_path.exists():
            raise SystemExit(f"Unexpected existing negative-test PNG: {capture_path}")
        try:
            result = subprocess.run(
                [str(fixture_bin / executable), "--smoke-test", f"--capture={capture_path}", "--capture-frame=120"],
                cwd=fixture_bin, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", timeout=90, check=False)
        except subprocess.TimeoutExpired as error:
            output = error.stdout or b""
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            artifact.with_suffix(".log").write_text(output + "\nNEGATIVE_TEST_TIMEOUT\n", encoding="utf-8")
            raise SystemExit(f"G1 negative case timed out, not an expected failure: {name}")
        artifact.with_suffix(".log").write_text(result.stdout, encoding="utf-8")
        passed = (result.returncode == 1 and "SMOKE_TEST_FAILED" in result.stdout
                  and "SMOKE_TEST_OK" not in result.stdout and not capture_path.exists()
                  and re.search(expected, result.stdout) is not None)
        results.append({"case": name, "status": "pass" if passed else "fail",
                        "exit_code": result.returncode, "capture_created": capture_path.exists(),
                        "expected_reason": expected})
        (capture_dir / f"{app}-negative-results.json").write_text(
            json.dumps({"scope": "input rejection only; not pose or physics acceptance", "cases": results}, indent=2) + "\n",
            encoding="utf-8")
        if not passed:
            print(result.stdout, file=sys.stderr)
            raise SystemExit(f"G1 negative case did not fail as expected: {name} (exit {result.returncode})")
        print(f"G1 negative {name}: OK (exit 1, expected reason, no success marker, no PNG)", flush=True)
PY
