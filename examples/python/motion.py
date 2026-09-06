"""Strict canonical-data loading and rigid interpolation; no window/physics imports.

Copyright (c) 2026 Daito Manabe. SPDX-License-Identifier: MIT
"""
from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

LABEL = "KINEMATIC REFERENCE — PHYSICS NOT VALIDATED"
DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data" / "reference"


class DataError(ValueError):
    """Invalid or unsupported input, never a graphics fallback."""


def integer(value, label):
    if type(value) is not int or not -(2**31) <= value < 2**31:
        raise DataError(f"{label} must be an exact 32-bit JSON integer")
    return value


def number(value, label):
    if type(value) not in (int, float) or not np.isfinite(value):
        raise DataError(f"{label} must be a finite JSON number")
    if abs(value) > float(np.finfo(np.float32).max):
        raise DataError(f"{label} is outside the graphics float range")
    return float(value)


def array(value, shape, label):
    def check(items, dimensions):
        if not dimensions:
            return number(items, label)
        if not isinstance(items, list) or len(items) != dimensions[0]:
            raise DataError(f"{label} has the wrong array shape (expected {shape})")
        return [check(item, dimensions[1:]) for item in items]
    return np.asarray(check(value, shape), dtype=np.float64)


def names(value, label):
    if not isinstance(value, list) or not value or any(type(x) is not str or not x for x in value):
        raise DataError(f"{label} must contain nonempty names")
    if len(set(value)) != len(value):
        raise DataError(f"{label} contains duplicate names")
    return tuple(value)


def parents(value, count, label):
    if not isinstance(value, list) or len(value) != count:
        raise DataError(f"{label} has the wrong length")
    result = np.array([integer(x, label) for x in value], dtype=np.int32)
    if result[0] != -1 or any(not 0 <= result[i] < i for i in range(1, count)):
        raise DataError(f"{label} needs one root (-1) and parent-before-child order")
    return result


def unit_quaternions(q, label):
    norms = np.linalg.norm(q, axis=-1)
    if not np.all(np.isfinite(norms)) or np.max(np.abs(norms - 1)) > 1e-4:
        raise DataError(f"{label} must contain unit WXYZ quaternions")
    # Only remove the decimal-export roundoff after validating the actual norm.
    return q / norms[..., None]


def product(a, b):
    a, b = np.asarray(a), np.asarray(b)
    w = a[..., :1] * b[..., :1] - np.sum(a[..., 1:] * b[..., 1:], axis=-1, keepdims=True)
    xyz = a[..., :1] * b[..., 1:] + b[..., :1] * a[..., 1:] + np.cross(a[..., 1:], b[..., 1:])
    return np.concatenate((w, xyz), axis=-1)


def conjugate(q):
    return np.asarray(q) * np.array([1, -1, -1, -1])


def rotate(q, vector):
    t = 2 * np.cross(q[..., 1:], vector)
    return vector + q[..., :1] * t + np.cross(q[..., 1:], t)


def slerp(a, b, t):
    """Shortest-arc interpolation of already validated unit WXYZ quaternions."""
    dot = np.sum(a * b, axis=-1, keepdims=True)
    b = np.where(dot < 0, -b, b)
    dot = np.clip(np.abs(dot), 0, 1)
    angle = np.arccos(dot)
    denominator = np.maximum(np.sin(angle), 1e-12)
    wa = np.where(dot > 0.9995, 1 - t, np.sin((1 - t) * angle) / denominator)
    wb = np.where(dot > 0.9995, t, np.sin(t * angle) / denominator)
    result = wa * a + wb * b
    return result / np.linalg.norm(result, axis=-1, keepdims=True)


def local_rotations(world, parent_ids):
    local = world.copy()
    for body in range(1, len(parent_ids)):
        local[..., body, :] = product(conjugate(world[..., parent_ids[body], :]), world[..., body, :])
    return local


def interpolate(a_position, b_position, a_local, b_local, parent_ids, offsets, t):
    """Interpolate local rotations and reconstruct the fixed-offset body hierarchy."""
    blend = np.asarray(t)
    local = slerp(a_local, b_local, blend[..., None, None])
    rotations = local.copy()
    positions = np.empty_like(a_position, dtype=np.float64)
    positions[..., 0, :] = (1 - blend[..., None]) * a_position[..., 0, :] + blend[..., None] * b_position[..., 0, :]
    for body in range(1, len(parent_ids)):
        parent = parent_ids[body]
        positions[..., body, :] = positions[..., parent, :] + rotate(rotations[..., parent, :], offsets[body])
        rotations[..., body, :] = product(rotations[..., parent, :], local[..., body, :])
    return positions, rotations


def transform(position, q):
    w, x, y, z = q
    result = np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w), 2*(x*z + y*w), position[0]],
        [2*(x*y + z*w), 1 - 2*(x*x + z*z), 2*(y*z - x*w), position[1]],
        [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x*x + y*y), position[2]],
        [0, 0, 0, 1]], dtype=np.float64)
    return result


@dataclass
class Clip:
    name: str
    positions: np.ndarray
    rotations: np.ndarray
    local: np.ndarray
    source: np.ndarray
    parents: np.ndarray
    offsets: np.ndarray
    fps: float

    @property
    def duration(self):
        return len(self.positions) / self.fps

    def sample(self, seconds):
        if not np.isfinite(seconds) or seconds < 0:
            raise DataError("sample time must be finite and nonnegative")
        frame = (seconds % self.duration) * self.fps
        a = min(int(frame), len(self.positions) - 1)
        b = min(a + 1, len(self.positions) - 1)
        t = frame - a
        pos, rot = interpolate(self.positions[a], self.positions[b], self.local[a], self.local[b],
                               self.parents, self.offsets, t)
        return pos, rot, (1 - t) * self.source[a] + t * self.source[b]

    def display_offset(self, slot):
        return np.array([-self.positions[0, 0, 0], 1.8 * slot - self.positions[0, 0, 1], 0.0])

    def sample_many(self, seconds):
        """Identical rigid interpolation batched over history times, not a linear joint shortcut."""
        seconds = np.asarray(seconds, dtype=np.float64)
        if seconds.ndim != 1 or not np.isfinite(seconds).all() or np.any(seconds < 0):
            raise DataError("history times must be finite, nonnegative and one-dimensional")
        frames = (seconds % self.duration) * self.fps
        a = np.minimum(frames.astype(np.int64), len(self.positions) - 1)
        b = np.minimum(a + 1, len(self.positions) - 1)
        return interpolate(self.positions[a], self.positions[b], self.local[a], self.local[b],
                           self.parents, self.offsets, frames - a)


@dataclass
class Mesh:
    body: int
    geometry: np.ndarray  # Expanded flat-shaded triangles, XYZ + normal XYZ.
    local: np.ndarray
    color: np.ndarray


class Motion:
    def __init__(self, data, model):
        try:
            self._load(data, model)
        except (KeyError, TypeError, OverflowError, IndexError) as exc:
            raise DataError(f"Missing or malformed canonical data: {exc}") from exc

    def _load(self, data, model):
        if integer(data["schema_version"], "motion schema_version") != 1:
            raise DataError("Unsupported motion schema")
        if integer(model["schema_version"], "model schema_version") != 1:
            raise DataError("Unsupported model schema")
        self.fps = number(data["fps"], "fps")
        if self.fps <= 0:
            raise DataError("fps must be positive")
        if data["validation"]["label"] != LABEL:
            raise DataError("Missing kinematic-reference validation label")
        self.pose_passed = data["validation"].get("pose_status") == "pass"
        self.body_names = names(data["body_names"], "body_names")
        self.parents = parents(data["body_parents"], len(self.body_names), "body_parents")
        self.offsets = array(data["body_offsets"], (len(self.parents), 3), "body_offsets")
        self.source_names = names(data["source_names"], "source_names")
        self.source_parents = parents(data["source_parents"], len(self.source_names), "source_parents")
        self.source_start_frame = integer(data["source_start_frame"], "source_start_frame")
        self.source_time_offset = number(data["source_time_offset_s"], "source_time_offset_s")
        if self.source_start_frame < 0 or self.source_time_offset < 0:
            raise DataError("Source offsets cannot be negative")
        self.clips = []
        if not isinstance(data["clips"], list) or len(data["clips"]) != 3:
            raise DataError("Expected three clips A, B, C")
        for recording, expected in zip(data["clips"], "ABC"):
            if recording["name"] != expected:
                raise DataError("Clip order must be A, B, C")
            frames = recording["frames"]
            if not isinstance(frames, list) or len(frames) < 2:
                raise DataError("Each clip needs at least two frames")
            positions = np.stack([array(f["positions"], (len(self.parents)*3,), "positions").reshape(-1, 3) for f in frames])
            world = np.stack([array(f["rotations"], (len(self.parents)*4,), "rotations").reshape(-1, 4) for f in frames])
            world = unit_quaternions(world, "body rotations")
            source = np.stack([array(f["source_positions"], (len(self.source_names)*3,), "source positions").reshape(-1, 3) for f in frames])
            for body in range(1, len(self.parents)):
                parent = self.parents[body]
                expected_position = positions[:, parent] + rotate(world[:, parent], self.offsets[body])
                if np.max(np.abs(expected_position - positions[:, body])) > 2e-5:
                    raise DataError("body_offsets do not match world key positions")
            self.clips.append(Clip(expected, positions, world, local_rotations(world, self.parents),
                                   source, self.parents, self.offsets, self.fps))
        if len({len(c.positions) for c in self.clips}) != 1:
            raise DataError("All three clips must have the same frame count")
        self.hands = [i for i, name in enumerate(self.body_names) if "wrist_yaw" in name or "hand" in name]
        self.meshes = []
        if not isinstance(model["meshes"], list) or not model["meshes"]:
            raise DataError("Model contains no meshes")
        for mesh in model["meshes"]:
            body = integer(mesh["body"], "mesh body")
            if not 0 <= body < len(self.parents):
                raise DataError("Mesh body is outside the skeleton")
            vertices, indices = mesh["vertices"], mesh["indices"]
            if not isinstance(vertices, list) or len(vertices) < 9 or len(vertices) % 3:
                raise DataError("Invalid mesh vertices")
            vertices = array(vertices, (len(vertices),), "vertices").reshape(-1, 3)
            if not isinstance(indices, list) or not indices or len(indices) % 3:
                raise DataError("Invalid triangle indices")
            indices = np.array([integer(i, "triangle index") for i in indices], dtype=np.int32)
            if indices.min() < 0 or indices.max() >= len(vertices):
                raise DataError("Triangle index out of bounds")
            triangles = vertices[indices].reshape(-1, 3, 3)
            normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
            lengths = np.linalg.norm(normals, axis=-1)
            drawable = lengths > 1e-10
            if not drawable.any():
                raise DataError("Mesh contains no drawable triangles")
            triangles, normals = triangles[drawable], normals[drawable] / lengths[drawable, None]
            geometry = np.concatenate((triangles, np.repeat(normals[:, None, :], 3, axis=1)), axis=2).reshape(-1, 6).astype("f4")
            if not np.isfinite(geometry).all():
                raise DataError("Mesh overflows graphics float precision")
            local = transform(array(mesh["position"], (3,), "mesh position"),
                              unit_quaternions(array(mesh["quaternion"], (4,), "mesh quaternion"), "mesh quaternion"))
            color = array(mesh["color"], (4,), "mesh color")
            if np.any((color < 0) | (color > 1)):
                raise DataError("Mesh color must be in 0..1")
            self.meshes.append(Mesh(body, geometry, local, color))

    @classmethod
    def load(cls, directory=DEFAULT_DATA):
        def read(filename):
            try:
                with (Path(directory) / filename).open(encoding="utf-8") as stream:
                    return json.load(stream, parse_constant=lambda value: (_ for _ in ()).throw(DataError(f"Non-finite JSON: {value}")))
            except (OSError, json.JSONDecodeError) as exc:
                raise DataError(f"Cannot load {filename}: {exc}") from exc
        return cls(read("g1-motion.json"), read("g1-model.json"))
