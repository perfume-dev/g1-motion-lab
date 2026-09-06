# Canonical data

`source/A_test.bvh`, `B_test.bvh` and `C_test.bvh` are byte-identical copies of
the recordings bundled with the 2012 Perfume Global Site Project examples.
They have 1,300 frames at 40 Hz. Their original upstream location and commit
are recorded in [ORIGINS.md](../ORIGINS.md); the source files were not edited.

`reference/` contains one accepted 29-DOF Unitree G1 package: three 1,299-frame
40 Hz clips, model-derived visual meshes, complete pose QA and provenance.
The checked-in package is byte-identical to the version validated before this
repository was separated. Its original provenance is deliberately retained,
including its then-current upstream source repository. New exports identify
this repository as their input location and retain the original source origin.

[manifest.json](manifest.json) pins the sizes and SHA-256 hashes of all eight
canonical files. Run `python3 scripts/prepare-data.py --check` from the repository
root to verify those hashes, full clip coverage and the carried pose reports.
This integrity check is not a fresh retarget or physical simulation.

Native viewers receive disposable copies through `scripts/prepare-data.py`;
Python reads this canonical directory directly. Do not manually maintain
separate versions of the same motion package inside individual examples.

## Rights and validation boundaries

- The first-party code MIT license does **not** relicense these source or
  derived performance recordings. Original performance-data terms remain
  unchanged; do not infer permission for music, likeness, branding or endorsement.
- G1 model-derived geometry retains the supplied
  [Unitree BSD-3-Clause notice](reference/MODEL-LICENSE). Visual hulls are not
  substituted for a physical simulator's original collision/inertial model.
- [Pose QA](reference/pose_retarget_qa.json) records kinematic acceptance only.
  [Provenance](reference/provenance.json) pins source/model/URDF/mesh assets.
  Balance, self-collision clearance, finite-force tracking and hardware safety
  are not approved. See [measured limitations](../docs/VALIDATION.md).
