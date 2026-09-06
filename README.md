# Perfume / G1 Motion Lab

Perfumeのモーションキャプチャー（BVH）からUnitree G1の動きを生成・検証し、
openFrameworks・Processing・Pythonで再生するためのリポジトリです。

An independent home for **Perfume BVH → Unitree G1** motion studies:
constrained retargeting, measured pose validation, and three lightweight viewers.
The bundled A/B/C references use real G1 model-derived meshes and include the
original human skeleton for comparison. No music or audio is bundled.

**Kinematic reference only — physics and real-robot execution are not approved.**
There are no actuator commands, robot SDKs, DDS endpoints, or learned-controller
weights in this repository. A separate tracking experiment failed self-contact
checks. An attractive dance preview is not proof that a physical robot can do it.
See [validation and limitations](docs/VALIDATION.md).

## Choose a viewer

| Example | Requirements | What it does |
| --- | --- | --- |
| [openFrameworks](examples/openframeworks/README.md) | openFrameworks 0.12.1, desktop OpenGL | Rigid-link G1 meshes, hand trails, human-source overlay, orbit controls |
| [Processing](examples/processing/g1_motion_lab/README.md) | Processing 4.5.6 | The same reference data as a self-contained P3D sketch |
| [Python](examples/python/README.md) | Python and the small viewer dependency set | Native OpenGL playback, source comparison and deterministic captures; no IK environment required |

Install only the viewer you want; you do not need all three environments.
All three use the **same checked-in canonical data**. There is no server to
start and no paid API or cloud account is required for playback.

```sh
git clone https://github.com/perfume-dev/g1-motion-lab.git
cd g1-motion-lab
python3 scripts/prepare-data.py --check
```

For Python, with [uv](https://docs.astral.sh/uv/) installed:

```sh
uv sync --frozen --project examples/python --python 3.12
uv run --frozen --project examples/python python examples/python/viewer.py
```

For Processing, stage the data and open the sketch:

```sh
python3 scripts/prepare-data.py --viewer processing
```

Open `examples/processing/g1_motion_lab/g1_motion_lab.pde` and press Run.
For openFrameworks, its build helper stages the data automatically:

```sh
./scripts/build-openframeworks.sh /absolute/path/to/openFrameworks
```

The [Python guide](examples/python/README.md) covers controls and rendering checks.
Viewer setup never runs a retarget, downloads robot weights,
or connects to hardware. Generated native-viewer data copies are ignored by Git;
the preparation script refuses to overwrite an edited copy.

## From BVH to the dancing model

1. **Source** — the unchanged 2012 Perfume A/B/C BVH recordings in `data/source`.
2. **Retarget and validate** — the [Python reproduction kit](tools/g1-retarget/README.md)
   adapts human proportions to the pinned 29-DOF G1 and checks original frames.
3. **Inspect** — OF, Processing and Python display the accepted reference package
   in `data/reference`, keeping robot links rigid between samples.

You can immediately play the supplied package. Recomputing it is optional and
belongs on a separate workstation. The current IK/path solver uses CPU; a GPU
does not automatically accelerate it. The guide records the tested remote
workflow, time costs, source assumptions and exact model pins. It does not
provision machines or authorize paid cloud compute.

All three clips pass the recorded kinematic pose gates at **1,299 frames each,
40 Hz**. Original frame 0 is retained in BVH but excluded from the derived dance
because of its discontinuity. Playback starts at source time 0.025 s.
The viewer loop reset is not a physically validated transition.

![openFrameworks G1 reference viewer; physics not validated](docs/images/openframeworks.png)

## Repository map

```text
data/source/             Original BVH recordings
data/reference/          One canonical motion/model/QA package
examples/openframeworks/ Native C++ viewer
examples/processing/     Processing sketch
examples/python/         Python viewer
tools/g1-retarget/       BVH parser, constrained solver, independent export gates
scripts/                 Data preparation and build/render checks
tests/                   Data and viewer regression checks
```

Human and robot proportions differ. Presentation layout is not the original
stage formation, and the viewers expose their recentering conventions.
Visual validation, pose agreement and physical feasibility remain separate.
See [standalone verification](docs/REPOSITORY_VERIFICATION.md) for actual
application captures, test scope and reproducible checks.

## Origins, maintenance and rights

Maintained by **Daito Manabe** under `perfume-dev`. This project was extracted
from the maintained [openFrameworks](https://github.com/perfume-dev/example-openFrameworks)
and [Processing](https://github.com/perfume-dev/example-processing) example collections.
[ORIGINS.md](ORIGINS.md) records exact source commits and the original history;
the older repositories remain the record of their historical development.

[MIT](LICENSE) covers first-party code and documentation, **not** the original
or derived Perfume performance data or Unitree model assets. The model retains
its upstream BSD-3-Clause notice. See [data provenance](data/README.md) and
[LICENSES.md](LICENSES.md); publication does not grant additional performance,
music, artist-name or endorsement rights.
