# Python viewer validation

Verified on 2026-09-06 with Python 3.12.13, the committed `uv.lock`, and macOS Apple Silicon. Actual context: OpenGL `4.1 Metal - 90.5`, renderer `Apple M5 Max`. Logical 1280×800 windows produced 2560×1600 Retina framebuffers. All automated windows remained hidden and unfocused.

Command from the repository root:

```sh
uv sync --frozen --project examples/python --python 3.12
bash scripts/verify-python.sh
```

- **17 unit tests passed**, with warnings treated as errors. Coverage includes fixed-offset rotating chains, shortest quaternion paths, parent-local reconstruction, batch/scalar interpolation equivalence, loop boundaries, pause/reset, exact JSON integers, finite values, unit quaternion norms, hierarchy/mesh validation, and all three canonical 1,299-frame clips. The malformed-value test contains 23 separate cases.
- **Seven actual OpenGL captures passed**: 8 seconds, 16 seconds, source overlay, A individually, a fractional frame at 14.3125 seconds, a narrow window, and a deliberately failed-pose diagnostic warning.
- The 8-second control check exercised all three solo selections, all-clips selection, source toggle, pause/reset, orbit/zoom, help hiding and resizing through the real viewer callback/render paths.
- All three 8-second robots produced actual mesh-only depth-tested sample counts of **56,242 / 47,174 / 43,810**. Floor, trails, human overlay and HUD are excluded from these queries. Pixel readback independently contained 64,225 bright scene pixels.
- Scene-only changed-pixel ratios, excluding the HUD/footer: **4.3633%** for 8→16 seconds and **0.1264%** for source overlay on/off. These exceed the respective 0.2% and 0.03% gates.
- **Two real CLI negative-input tests passed**: non-integer schema and inconsistent fixed body offsets both exited nonzero with `G1_DATA_ERROR`, no PNG, and no success marker.
- Screenshots were visually inspected for complete bodies, readable white/dark mesh materials, source overlay alignment, unbroken mesh articulation, narrow framing, and the persistent kinematic/failed-pose labels. The bundled font's missing em-dash glyph is rendered explicitly in the permanent label.

The final local evidence set is under ignored `artifacts/python/run-fhpodoeb/` (PNGs, per-run logs/JSON, and `summary.json`). Evidence directories are uniquely named on each verification run.

A bounded hidden render probe of 60 consecutive full three-robot frames completed in 0.880 seconds (68.18 frames/s) on this Mac, including the smoke occlusion checks. This is a local throughput measurement, not a cross-platform frame-rate guarantee. Batched hand-history interpolation uses the same fixed-offset math as single-pose interpolation.

Linux Mesa/Xvfb has a dedicated CI invocation; this macOS record does not certify a Linux result. Neither the unit tests nor graphics checks validate dynamics, self-collision, balance, contact, torque, policies, or real hardware. The display remains **KINEMATIC REFERENCE — PHYSICS NOT VALIDATED**.
