# Origins and historical attribution

This repository was created on 2026-09-06 by Daito Manabe as the independent
home for Perfume BVH-to-G1 studies. It imports **source snapshots**, not rewritten
histories of the original repositories. Historical commits remain accessible
at the immutable links below; no original Git history was deleted or replaced.

| Component | Imported from |
| --- | --- |
| OF viewer and shared render-test runtime | [example-openFrameworks at 71c0a636](https://github.com/perfume-dev/example-openFrameworks/tree/71c0a6363a5f504aa3ecc190fcd3067b3fc2fadf) — `example-g1-motion-lab`, relevant `shared/ExampleRuntime.h` checks |
| Processing viewer and tests | [example-processing at 87cdffb1](https://github.com/perfume-dev/example-processing/tree/87cdffb12ea627c687434670b67b6bf27a941ece) — `g1_motion_lab`, `tests/g1` |
| Retarget/reproduction kit | [tools/g1-retarget](https://github.com/perfume-dev/example-openFrameworks/tree/71c0a6363a5f504aa3ecc190fcd3067b3fc2fadf/tools/g1-retarget) |
| Original A/B/C recordings | [example-bvh/bin/data](https://github.com/perfume-dev/example-openFrameworks/tree/71c0a6363a5f504aa3ecc190fcd3067b3fc2fadf/example-bvh/bin/data) |
| Accepted reference package | [original G1 export](https://github.com/perfume-dev/example-openFrameworks/tree/71c0a6363a5f504aa3ecc190fcd3067b3fc2fadf/example-g1-motion-lab/bin/data) |

The OF-specific BVH-addon dependency is removed from the G1-only viewer; no
historical BVH addon or marching-cubes source is copied into this repository.
The Python viewer is new. Original recordings, accepted trajectories, model
geometry and their provenance are preserved byte-for-byte during separation.

The Perfume Global Site Project was made by many artists, choreographers,
designers, programmers, engineers and production supporters. Refer to the
[original contributors record](https://github.com/perfume-dev/example-openFrameworks/blob/71c0a6363a5f504aa3ecc190fcd3067b3fc2fadf/CONTRIBUTORS.md)
and [Agency for Cultural Affairs project record](https://www.bunka.go.jp/j-mediaarts-festival/award/single/perfume_global_site_project/index.html).
Stewardship and this new repository do not replace those individual credits.

Robot geometry is derived from Unitree's model in MuJoCo Menagerie revision
`8161bba264d7fa7c99ca301e91e7fb44737676ad`. Manufacturer velocity limits come from
Unitree ROS revision `7d6075f7f58588b189b940130e3edab3c839b2df`.
Exact file hashes and notices remain in `data/reference` and the retarget kit.
