# G1 Motion Lab

A Processing 4.5.6 viewer for three BVH-to-G1 kinematic reference clips. It draws
the actual exported G1 body geometry with retained `PShape` meshes and composes
body/world transforms with `PMatrix3D`. It does not perform retargeting locally
or send commands to a robot.

## Quick start

From the repository root, prepare the viewer's local data folder once:

```sh
python3 scripts/prepare-data.py --viewer processing
```

Then open `examples/processing/g1_motion_lab/g1_motion_lab.pde` in Processing
4.5.6 and press Run. No external Processing libraries are required. Python is
used only for this preparation step; it does not run during playback.

The canonical package lives in [`data/reference`](../../../data/reference).
Preparation copies its five files into this sketch's ignored `data/` folder.
Do not edit those local copies. If a future update changes the canonical package,
move the old staged `data/` folder to a backup location before preparing again:
preparation deliberately refuses to overwrite different existing files.
Until the files are prepared, the viewer reports a missing-data error; no dummy
or procedural motion is substituted. The model package includes its own upstream license;
the MIT license in this folder covers the newly written sketch code only.

The installed package contains A/B/C at 40 Hz, with 1,299 dance frames per clip.
Original calibration frame 0 is excluded: playback starts at source time 0.025 s
and the final sample corresponds to source time 32.475 s. All three full clips
pass the independent kinematic pose gates recorded in
[`pose_retarget_qa.json`](../../../data/reference/pose_retarget_qa.json); input/model hashes are
recorded in [`provenance.json`](../../../data/reference/provenance.json). This approval is for
the kinematic reference only, not physics, contact stability, or hardware use.

## Controls

| Key / gesture | Action |
| --- | --- |
| 1 / 2 / 3 | A / B / C alone |
| 0 | All three |
| O | Original human skeleton overlay |
| Space | Pause / resume |
| R | Restart and reset camera |
| Drag | Orbit / elevation |
| H | Toggle help |
| S | Save under `captures/` |

The cyan lines show short hand trajectories. Both robot and human source
receive the same display translation: remove the robot's initial horizontal
origin, then offset each clip for the three-column view. Later travel and
robot/source differences are retained. The data itself is not changed.
The default camera presents A, B, C from left to right, matching the openFrameworks
viewer. These columns are display offsets, not the original stage formation.

The footer always states **KINEMATIC REFERENCE — PHYSICS NOT VALIDATED**,
including saved test frames. Visible motion is not proof of contact stability,
balance, actuator feasibility, or readiness for a real robot.
When `validation.pose_status` is anything other than `pass` (including missing),
the additional **POSE QA FAILED — DIAGNOSTIC ONLY** warning remains visible even
with help hidden. A successful render test does not approve that motion data.

## Data contract

`g1-motion.json` uses schema version 1 and includes `fps`, `body_names`,
`body_parents`, `body_offsets`, `source_names`, `source_parents`, and A/B/C `clips`. Each frame
has flat world-space `positions` (XYZ metres, Z-up), world-space `rotations`
(quaternions WXYZ), and matching `source_positions`. Robot/source coordinates
must share the same origin and orientation for the overlay to be meaningful.
The validation object contains the exact footer label above and `pose_status`.
`body_offsets` contains one fixed parent-local `[x,y,z]` offset per body, in metres,
from the official model. The body order must be topological: body 0 has parent -1,
and every other body has a nonnegative parent index smaller than its own.
The root offset is present for completeness; root translation comes from the motion.
The loader checks fixed offsets against every world key position (20 micrometres
per-axis tolerance for export rounding), rejecting inconsistent packages.

`g1-model.json` also uses schema version 1 and contains a `meshes` array. Each mesh names a body index,
local `vertices`, triangle `indices`, its body-local `position` and WXYZ
`quaternion`, and RGBA `color` in 0..1. Geometry is retained on the GPU after
loading. The viewer uses the material brightness to preserve dark parts while
presenting the body in a restrained off-white/ink palette.
Schema versions, hierarchy parents, body references and triangle indices must
be JSON integers within the signed 32-bit range; decimal values, numeric strings
and overflowing integers are rejected, not truncated by Processing's `getInt()`.

The root position interpolates linearly and its world quaternion uses shortest-arc
SLERP. Child quaternions are converted from world rotations to parent-relative
rotations, interpolated, then composed through the hierarchy. Child positions come
from the fixed offsets, so connected body anchors cannot separate between samples.
Hand trails use that same rigid interpolation. The comparison human skeleton uses
linear interpolation of the source positions. Each clip holds its last sample before restarting;
the restart is a visualization boundary, not a physically smooth trajectory.

## Deterministic verification

From the repository root, with a JDK 17+ available:

```sh
python3 scripts/prepare-data.py --viewer processing
./scripts/verify-processing.sh /path/to/Processing artifacts/processing
```

The standalone suite renders 8, 16, 14.3 and 14.3125 seconds plus a source-overlay
view, checks that the images change, and rejects 20 malformed/missing G1 packages.
It also performs the preparation step, refusing to overwrite locally changed data.
The 14.3125-second capture exercises a genuine half-frame at 40 Hz. Negative tests
use disposable copies, never the canonical package or the prepared sketch data.
Linux automation should wrap the verifier with `xvfb-run --auto-servernum`.

To capture one frame directly:

```sh
/path/to/Processing cli --sketch=/path/to/g1_motion_lab \
  --output=/path/to/a-new-build-directory --run \
  --smoke-test --time=8 --capture=/absolute/path/to/g1.png
```

The test checks data shape, finite values, quaternion validity, hierarchy
indices, triangle indices, and actual visible model pixels. Missing data fails.
The test suite also compiles the exact pure-Java interpolation helper and checks
rotating three-body chains, rigid subframe anchors and quaternion sign changes.
The validation footer is excluded from the pixel test. Test launches suppress
window focus requests. The verifier also suppresses macOS Dock activation;
for direct macOS CLI captures set `JAVA_TOOL_OPTIONS=-Dapple.awt.UIElement=true`.
Add `--source-overlay` to capture the comparison, or `--clip=A` (also B/C) to
capture one recording. These options use the same drawing paths as the controls.

The supplied exports and their provenance must be verified separately before
calling the data physically executable. This sketch only verifies visualization.

The same repository contains the [remote reproduction kit](../../../tools/g1-retarget).
Python, IK and model-download dependencies stay on the selected compute
workstation; none are required to open this Processing sketch. The kit refuses
to make a viewer package unless all original A/B/C source frames pass its
independent pose gates. Neither it nor this viewer sends commands to hardware.
