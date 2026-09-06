"""Bounded real-graphics tests; outputs are ignored evidence, not canonical data.

Copyright (c) 2026 Daito Manabe. SPDX-License-Identifier: MIT
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
VIEWER = ROOT / "examples" / "python" / "viewer.py"


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    evidence = Path(tempfile.mkdtemp(prefix="run-", dir=output))
    records = {}
    variants = {
        "python-8": ["--time", "8", "--exercise-controls"],
        "python-16": ["--time", "16"],
        "python-overlay": ["--time", "8", "--source-overlay"],
        "python-solo": ["--time", "16", "--clip", "A"],
        "python-subframe": ["--time", "14.3125"],
        "python-narrow": ["--time", "8", "--width", "640", "--height", "800"],
    }
    def invoke(name, extra, expected_success=True):
        capture = evidence / (name + ".png")
        command = [sys.executable, str(VIEWER), "--smoke-test", "--capture", str(capture), *extra]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
        (evidence / (name + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
        if not expected_success:
            assert result.returncode != 0, f"{name}: malformed input was accepted"
            assert "G1_DATA_ERROR" in result.stderr, f"{name}: not a data rejection: {result.stderr}"
            assert "SMOKE_TEST_OK" not in result.stdout and not capture.exists(), f"{name}: false success evidence"
            records[name] = dict(status="EXPECTED_DATA_REJECTION", exit_code=result.returncode)
            return
        assert result.returncode == 0, f"{name}: {result.stdout}\n{result.stderr}"
        report = json.loads(capture.with_suffix(".json").read_text(encoding="utf-8"))
        assert report["status"] == "SMOKE_TEST_OK", report
        assert report["visible"] is False and report["focused"] is False, report
        assert report["mesh_count"] == 35 and min(report["mesh_samples"]) >= 150, report
        assert report["readback_scene_pixels"] >= 150 and capture.is_file(), report
        records[name] = report
        print(f"PASS {name}: samples={report['mesh_samples']} framebuffer={report['framebuffer']}", flush=True)
    for name, flags in variants.items():
        invoke(name, flags)
    # Compare only the scene: time text and footer cannot create animation/overlay evidence.
    def pixels(name):
        image = np.asarray(Image.open(evidence / f"{name}.png").convert("RGB"), dtype=np.int16)
        return image[int(image.shape[0] * .20):int(image.shape[0] * .86)]
    for name, minimum in (("python-16", .002), ("python-overlay", .0003)):
        difference = np.max(np.abs(pixels("python-8") - pixels(name)), axis=-1) > 12
        ratio = float(difference.mean())
        assert ratio > minimum, f"{name}: unchanged scene ({ratio})"
        records[name]["changed_scene_ratio_vs_8"] = ratio
    # Exercise actual loader/CLI failure before any window can be created.
    data = json.loads((ROOT / "data/reference/g1-motion.json").read_text())
    model = json.loads((ROOT / "data/reference/g1-model.json").read_text())
    fixture = evidence / "negative-fixture"
    fixture.mkdir()
    (fixture / "g1-model.json").write_text(json.dumps(model))
    data["schema_version"] = 1.0
    (fixture / "g1-motion.json").write_text(json.dumps(data))
    invoke("negative-schema", ["--data", str(fixture)], expected_success=False)
    data["schema_version"] = 1
    data["body_offsets"][1][0] += .1
    (fixture / "g1-motion.json").write_text(json.dumps(data))
    invoke("negative-offset", ["--data", str(fixture)], expected_success=False)
    data["body_offsets"][1][0] -= .1
    data["validation"]["pose_status"] = "fail"
    (fixture / "g1-motion.json").write_text(json.dumps(data))
    invoke("python-pose-warning", ["--time", "8", "--data", str(fixture)])
    assert records["python-pose-warning"]["pose_status"] == "fail_or_unknown"
    # A warning is a diagnostic render, never a pose/physics approval.
    normal = np.asarray(Image.open(evidence / "python-8.png"), dtype=np.int16)
    failed = np.asarray(Image.open(evidence / "python-pose-warning.png"), dtype=np.int16)
    footer_diff = np.max(np.abs(normal[-int(normal.shape[0]*.08):] - failed[-int(failed.shape[0]*.08):]), axis=-1) > 12
    assert np.count_nonzero(footer_diff) > 100, "Pose warning is not visible in the framebuffer"
    result = dict(status="PYTHON_VIEWER_CHECKS_OK", evidence_directory=str(evidence), checks=records)
    (evidence / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"PYTHON_VIEWER_CHECKS_OK {evidence}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.output.resolve())
