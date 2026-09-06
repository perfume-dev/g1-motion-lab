"""Numeric/loader regressions; no context, window, server or robot connection.

Copyright (c) 2026 Daito Manabe. SPDX-License-Identifier: MIT
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "examples" / "python"))
from motion import (LABEL, Clip, DataError, Motion, conjugate, interpolate, integer,
                    local_rotations, product, rotate, slerp, transform)
from viewer import Playback, arguments, camera


def fixture():
    frames = []
    for angle in (0.0, np.pi):
        q = np.array([np.cos(angle/2), 0, 0, np.sin(angle/2)])
        positions = [[0, 0, 1], rotate(q, np.array([1, 0, 0])) + [0, 0, 1], rotate(q, np.array([2, 0, 0])) + [0, 0, 1]]
        frames.append(dict(positions=np.array(positions).reshape(-1).tolist(), rotations=np.tile(q, 3).tolist(),
                           source_positions=[0, 0, 1, 1, 0, 1]))
    data = dict(schema_version=1, fps=40.0, validation=dict(label=LABEL, pose_status="pass"),
                body_names=["root", "child", "tip"], body_parents=[-1, 0, 1],
                body_offsets=[[0, 0, 0], [1, 0, 0], [1, 0, 0]],
                source_names=["root", "tip"], source_parents=[-1, 0],
                source_start_frame=1, source_time_offset_s=0.025,
                clips=[dict(name=name, frames=copy.deepcopy(frames)) for name in "ABC"])
    model = dict(schema_version=1, meshes=[dict(body=0, vertices=[0, 0, 0, 1, 0, 0, 0, 1, 0],
                                               indices=[0, 1, 2], position=[0, 0, 0],
                                               quaternion=[1, 0, 0, 0], color=[1, 1, 1, 1])])
    return data, model


class RigidTests(unittest.TestCase):
    def test_rotating_chain_keeps_length(self):
        motion = Motion(*fixture())
        p, q, source = motion.clips[0].sample(0.0125)
        np.testing.assert_allclose(p, [[0, 0, 1], [0, 1, 1], [0, 2, 1]], atol=1e-12)
        np.testing.assert_allclose(np.linalg.norm(np.diff(p, axis=0), axis=1), [1, 1], atol=1e-12)

    def test_local_rotation_child_not_world_lerp(self):
        parent = np.array([-1, 0, 1])
        offsets = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 0]])
        q0 = np.tile([1., 0, 0, 0], (3, 1))
        q1 = np.array([[0., 0, 0, 1], [1., 0, 0, 0], [1., 0, 0, 0]])
        p, q = interpolate(np.zeros((3, 3)), np.zeros((3, 3)), q0, q1, parent, offsets, .5)
        np.testing.assert_allclose(p[2], [0, 2, 0], atol=1e-12)
        np.testing.assert_allclose(q[0], q[2], atol=1e-12)

    def test_quaternion_sign_invariance(self):
        q = np.array([np.sqrt(.5), 0, np.sqrt(.5), 0])
        for t in (0, .25, .5, 1):
            np.testing.assert_allclose(slerp(q, -q, t), q, atol=1e-12)

    def test_local_world_round_trip(self):
        world = np.array([[1., 0, 0, 0], [np.sqrt(.5), np.sqrt(.5), 0, 0], [0., 0, 1, 0]])
        local = local_rotations(world, [-1, 0, 1])
        np.testing.assert_allclose(product(world[1], local[2]), world[2], atol=1e-12)
        np.testing.assert_allclose(product(conjugate(world[1]), world[1]), [1, 0, 0, 0], atol=1e-12)

    def test_transform_and_rotate_agree(self):
        q = np.array([np.sqrt(.5), 0, 0, np.sqrt(.5)])
        m = transform([2, 3, 4], q)
        np.testing.assert_allclose((m @ [1, 0, 0, 1])[:3], rotate(q, np.array([1, 0, 0])) + [2, 3, 4])

    def test_end_hold_then_loop(self):
        clip = Motion(*fixture()).clips[0]
        np.testing.assert_allclose(clip.sample(.049)[0], clip.sample(.025)[0], atol=1e-12)
        np.testing.assert_allclose(clip.sample(.05)[0], clip.sample(0)[0], atol=1e-12)

    def test_display_preserves_later_travel(self):
        clip = Motion(*fixture()).clips[0]
        clip.positions[:, :, 0] += 9
        np.testing.assert_allclose(clip.display_offset(-1), [-9, -1.8, 0])

    def test_invalid_sample_time(self):
        clip = Motion(*fixture()).clips[0]
        for value in (-1, np.inf, np.nan):
            with self.assertRaises(DataError):
                clip.sample(value)

    def test_batched_history_matches_scalar(self):
        clip = Motion(*fixture()).clips[0]
        times = np.array([0, .006, .0125, .023, .049, .05, .061])
        positions, rotations = clip.sample_many(times)
        for i, seconds in enumerate(times):
            pos, rot, _ = clip.sample(seconds)
            np.testing.assert_allclose(positions[i], pos, atol=1e-12)
            np.testing.assert_allclose(rotations[i], rot, atol=1e-12)


class LoaderTests(unittest.TestCase):
    def test_exact_integer(self):
        for value in (True, 1., "1", 2**31, -2**31 - 1):
            with self.assertRaises(DataError):
                integer(value, "test")

    def test_malformed_shapes_and_values(self):
        changes = [
            lambda d, m: d.update(schema_version=1.0),
            lambda d, m: d.update(fps="40"),
            lambda d, m: d.update(fps=0),
            lambda d, m: d.update(fps=True),
            lambda d, m: d.update(body_parents=[-1, 2, 1]),
            lambda d, m: d.update(body_parents=[-1, 0., 1]),
            lambda d, m: d.update(body_names=["same", "same", "tip"]),
            lambda d, m: d.update(body_offsets=[[0, 0, 0], [2, 0, 0], [1, 0, 0]]),
            lambda d, m: d["clips"][0]["frames"][0].update(positions=[0, 0]),
            lambda d, m: d["clips"][0]["frames"][0]["positions"].__setitem__(0, float("nan")),
            lambda d, m: d["clips"][0]["frames"][0]["positions"].__setitem__(0, "0"),
            lambda d, m: d["clips"][0]["frames"][0]["rotations"].__setitem__(0, 2),
            lambda d, m: d["clips"][0]["frames"].pop(),
            lambda d, m: d["clips"].reverse(),
            lambda d, m: d["validation"].update(label="physics validated"),
            lambda d, m: m["meshes"][0].update(body=3),
            lambda d, m: m["meshes"][0].update(body="0"),
            lambda d, m: m["meshes"][0].update(indices=[0, 1., 2]),
            lambda d, m: m["meshes"][0].update(indices=[0, 1, 3]),
            lambda d, m: m["meshes"][0].update(indices=[0, 0, 0]),
            lambda d, m: m["meshes"][0].update(quaternion=[0, 0, 0, 0]),
            lambda d, m: m["meshes"][0].update(color=[2, 1, 1, 1]),
            lambda d, m: m["meshes"][0]["vertices"].__setitem__(0, 1e300),
        ]
        for index, change in enumerate(changes):
            with self.subTest(case=index):
                data, model = fixture()
                change(data, model)
                with self.assertRaises(DataError):
                    Motion(data, model)

    def test_missing_and_bad_json(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DataError):
                Motion.load(directory)
            (Path(directory) / "g1-motion.json").write_text('{"fps":NaN}', encoding="utf-8")
            with self.assertRaises(DataError):
                Motion.load(directory)

    def test_failed_pose_remains_diagnostic(self):
        for status in ("fail", "pending", None):
            data, model = fixture()
            data["validation"]["pose_status"] = status
            self.assertFalse(Motion(data, model).pose_passed)

    def test_canonical_full_clip(self):
        motion = Motion.load()
        self.assertEqual([c.name for c in motion.clips], list("ABC"))
        self.assertEqual([len(c.positions) for c in motion.clips], [1299] * 3)
        self.assertEqual(len(motion.meshes), 35)
        self.assertEqual(motion.fps, 40.)
        self.assertEqual(motion.source_time_offset, .025)
        self.assertTrue(motion.pose_passed)
        for clip in motion.clips:
            for seconds in (0, 8, 16, 14.3125, 32.474, 32.475):
                pos, q, source = clip.sample(seconds)
                self.assertTrue(np.isfinite(pos).all())
                for body in range(1, len(motion.parents)):
                    np.testing.assert_allclose(np.linalg.norm(pos[body] - pos[motion.parents[body]]),
                                               np.linalg.norm(motion.offsets[body]), atol=1e-12)


class PlaybackTests(unittest.TestCase):
    def test_pause_resume_reset(self):
        clock = Playback(8, now=100)
        self.assertEqual(clock.seconds(102), 10)
        clock.toggle(102)
        self.assertEqual(clock.seconds(200), 10)
        clock.toggle(200)
        self.assertEqual(clock.seconds(203), 13)
        clock.reset(203)
        self.assertEqual(clock.seconds(204), 1)
        clock.toggle(204)
        clock.reset(205)
        self.assertEqual(clock.seconds(400), 0)

    def test_camera_resize_and_extremes_finite(self):
        for width, height in ((1280, 800), (640, 1200), (4096, 240)):
            for single in (False, True):
                vp, eye = camera(width, height, -.16, .13, 1., single)
                self.assertTrue(np.isfinite(vp).all())
                self.assertTrue(np.isfinite(eye).all())
                self.assertNotEqual(np.linalg.det(vp), 0.)

    def test_capture_implies_hidden(self):
        args = arguments(["--capture", str(Path(tempfile.gettempdir()) / "capture.png")])
        self.assertTrue(args.smoke_test)


if __name__ == "__main__":
    unittest.main()
