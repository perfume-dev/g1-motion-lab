# G1 Motion Lab — Python

A small local viewer of the same validated reference motion as the openFrameworks and Processing examples: three G1 robots, 35 actual exported mesh parts per robot, hand trails, and an optional original-human-motion overlay. It reads the shared `data/reference` files directly; there is no second data copy.

**KINEMATIC REFERENCE — PHYSICS NOT VALIDATED.** This is playback, not a physics simulator or robot controller. It has no MuJoCo, IK, learning-policy, SDK, DDS, robot connection, server, or listening port. A failed/unknown pose status stays visible as a diagnostic warning. The robots' side-by-side offsets are for comparison, not the original stage formation.

## Run

From the repository root, with [uv](https://docs.astral.sh/uv/) installed:

```sh
uv sync --frozen --project examples/python --python 3.12
uv run --frozen --project examples/python python examples/python/viewer.py
```

The isolated environment lives in ignored `examples/python/.venv`. Python 3.12 is the tested version; the dependency metadata permits 3.12–3.14. The lock file pins GLFW 2.10.2, ModernGL 5.12.0, NumPy 2.5.2, Pillow 12.3.0 and glcontext 3.0.0. No global packages are installed. The viewer requires an OpenGL 3.3 core context; macOS uses its forward-compatible core context. Drivers/libraries must be available on the host.

The regular launch creates one resizable interactive window. It never raises or refocuses itself on updates. Hidden tests never show or focus a window.

## Controls

| Key / input | Action |
| --- | --- |
| `0`, `1` / `2` / `3` | All clips, or A / B / C individually |
| `O` | Original human skeleton overlay |
| Space | Pause / resume |
| `R` | Restart time and reset orbit / zoom; preserves paused state |
| Left drag, scroll | Orbit, zoom |
| `H` | Toggle help; validation warnings stay visible |
| `S` | Save the current framebuffer to ignored `captures/` in the current working directory |
| Escape | Close |

The motion preserves fixed body offsets. At fractional frames the viewer converts world quaternions to parent-local rotations, takes their shortest-arc SLERP, then reconstructs the hierarchy. It does **not** independently interpolate every joint's world position. The root translation and original human overlay interpolate linearly. The final sample is held until the playback loop restarts; the end and beginning are not cross-faded. Motion starts after the source BVH calibration frame, with the original 0.025-second source-time offset retained in the data.

## Verify without showing a window

```sh
uv run --frozen --project examples/python python examples/python/viewer.py \
  --smoke-test --time 8 --capture /absolute/path/python-8.png
bash scripts/verify-python.sh
```

`--capture` itself implies hidden smoke mode and requires an absolute PNG path. Optional flags: `--time 16`, `--clip A`, `--source-overlay`, `--width 960 --height 720`, `--exercise-controls`. It writes a PNG plus a JSON evidence sidecar. Smoke success is `SMOKE_TEST_OK`; malformed data, context/shader/GL errors, visible/focused test windows, inadequate mesh coverage, and blank readback all fail nonzero.

The verification script runs numeric/loader unit tests, deterministic 8/16-second, fractional-time, overlay, individual, narrow-window, and diagnostic-warning graphics checks. It exercises actual control and resize callbacks, checks animation/overlay differences outside the HUD, and tests malformed schema/offset input through the real CLI. New uniquely named evidence directories are retained under ignored `artifacts/python`; nothing is silently overwritten or considered a physics acceptance test.

On Linux CI with Mesa, install system GLFW/OpenGL prerequisites and run under an existing display or Xvfb, for example:

```sh
# Ubuntu system packages (CI provisioning, not Python dependencies):
# libgl1-mesa-dri libglx-mesa0 libgl-dev libglfw3 libxkbcommon0 xvfb xauth
LIBGL_ALWAYS_SOFTWARE=1 xvfb-run -a \
  -s '-screen 0 1280x800x24 +extension GLX +render -noreset' \
  bash scripts/verify-python.sh
```

macOS graphics evidence is recorded in [VALIDATION.md](VALIDATION.md). Linux support is designed for Mesa/GLX and must be judged by its own CI result, not inferred from macOS.

The Linux `libgl-dev` package supplies the unversioned `libGL.so` name used by
glcontext. Having a working `glxinfo` with only `libGL.so.1` is not sufficient.

## Implementation / scope

`motion.py` contains strict JSON validation, parent-local quaternion interpolation and mesh preparation. `viewer.py` contains GLFW interaction, ModernGL retained vertex buffers/shaders, and a Pillow-generated text overlay. Mesh-only occlusion queries exclude the floor, human overlay, trails and HUD from render acceptance. CPU work is ordinary data loading/interpolation; only graphics rendering uses the GPU. There is no CUDA or retargeting compute in this example.

Primary API references: [GLFW window/context and focus hints](https://www.glfw.org/docs/latest/window_guide.html), [ModernGL documentation](https://moderngl.readthedocs.io/en/5.12.0/), [Pillow default font](https://pillow.readthedocs.io/en/stable/reference/ImageFont.html#PIL.ImageFont.load_default).

New Python code is MIT licensed under the repository license. Canonical robot/model data and source motion retain their separate notices in the root license index; playback does not change those rights.
