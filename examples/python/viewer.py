#!/usr/bin/env python3
"""G1 Motion Lab: local OpenGL playback, never robot control or physics.

Copyright (c) 2026 Daito Manabe. SPDX-License-Identifier: MIT
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import glfw
import moderngl
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from motion import DEFAULT_DATA, LABEL, DataError, Motion, transform


MESH_VERTEX = """#version 330
uniform mat4 model;
uniform mat4 view_projection;
in vec3 in_position;
in vec3 in_normal;
out vec3 world_normal;
out vec3 world_position;
void main() {
    vec4 p = model * vec4(in_position, 1.0);
    world_position = p.xyz;
    world_normal = mat3(model) * in_normal;
    gl_Position = view_projection * p;
}
"""
MESH_FRAGMENT = """#version 330
uniform vec3 material;
uniform vec3 eye;
in vec3 world_normal;
in vec3 world_position;
out vec4 color;
void main() {
    vec3 n = normalize(world_normal) * (gl_FrontFacing ? 1.0 : -1.0);
    vec3 key = normalize(vec3(1.0, -1.2, 2.4));
    vec3 rim = normalize(vec3(-1.0, 1.8, 1.0));
    vec3 v = normalize(eye - world_position);
    float diffuse = max(dot(n, key), 0.0);
    float fill = max(dot(n, rim), 0.0);
    float specular = pow(max(dot(n, normalize(key + v)), 0.0), 35.0);
    vec3 lit = material * (0.38 + 0.64 * diffuse + 0.32 * fill)
             + vec3(0.30, 0.37, 0.40) * specular;
    color = vec4(lit, 1.0);
}
"""
LINE_VERTEX = """#version 330
uniform mat4 view_projection;
in vec3 in_position;
void main() { gl_Position = view_projection * vec4(in_position, 1.0); }
"""
LINE_FRAGMENT = """#version 330
uniform vec4 ink;
out vec4 color;
void main() { color = ink; }
"""
HUD_VERTEX = """#version 330
in vec2 in_position;
in vec2 in_uv;
out vec2 uv;
void main() { uv = in_uv; gl_Position = vec4(in_position, 0.0, 1.0); }
"""
HUD_FRAGMENT = """#version 330
uniform sampler2D panel;
in vec2 uv;
out vec4 color;
void main() { color = texture(panel, uv); }
"""


def matrix_bytes(matrix):
    return np.asarray(matrix, dtype="f4").T.copy().tobytes()


def normalize(vector):
    return vector / np.linalg.norm(vector)


def camera(width, height, yaw, pitch, zoom, single):
    # World is right-handed, Z up. G1 faces +X; this is a shallow front three-quarter view.
    target = np.array([0.0, 0.0, 0.8])
    distance = max(6.4, 7.4 * height / max(width, 1)) * zoom * (0.57 if single else 1.0)
    eye = target + distance * np.array([math.cos(pitch)*math.cos(yaw), math.cos(pitch)*math.sin(yaw), math.sin(pitch)])
    forward = normalize(target - eye)
    right = normalize(np.cross(forward, np.array([0.0, 0.0, 1.0])))
    up = np.cross(right, forward)
    view = np.eye(4)
    view[:3, :3] = np.array([right, up, -forward])
    view[:3, 3] = -view[:3, :3] @ eye
    near, far = 0.05, 100.0
    f = 1 / math.tan(math.radians(42) / 2)
    projection = np.zeros((4, 4))
    projection[0, 0] = f * height / max(width, 1)
    projection[1, 1] = f
    projection[2, 2] = (far + near) / (near - far)
    projection[2, 3] = 2 * far * near / (near - far)
    projection[3, 2] = -1
    return projection @ view, eye


class Playback:
    """Clock state is independent from window focus, visibility and render frame rate."""
    def __init__(self, initial=0.0, now=None):
        self.offset = initial
        self.started = time.monotonic() if now is None else now
        self.paused = False

    def seconds(self, now=None):
        now = time.monotonic() if now is None else now
        return self.offset if self.paused else self.offset + now - self.started

    def toggle(self, now=None):
        now = time.monotonic() if now is None else now
        self.offset = self.seconds(now)
        self.started = now
        self.paused = not self.paused

    def reset(self, now=None):
        self.offset = 0.0
        self.started = time.monotonic() if now is None else now


class Viewer:
    def __init__(self, motion, args):
        self.motion, self.args = motion, args
        self.window = None
        self.ctx = None
        self.resources = []
        self.width, self.height = args.width, args.height
        self.selected = -1 if args.clip == "all" else "ABC".index(args.clip)
        self.overlay = args.source_overlay
        self.help = True
        self.yaw, self.pitch, self.zoom = -0.16, 0.13, 1.0
        self.playback = Playback(args.time)
        self.dragging = False
        self.cursor = None
        self.capture_requested = None
        self.frame_count = 0
        self.mesh_samples = []
        self.hud_texture = None
        self.glfw_errors = []

    def resource(self, item):
        self.resources.append(item)
        return item

    def open(self):
        glfw.set_error_callback(lambda code, message: self.glfw_errors.append(f"{code}: {message!r}"))
        if sys.platform == "darwin":
            glfw.init_hint(glfw.COCOA_MENUBAR, glfw.FALSE)
            glfw.init_hint(glfw.COCOA_CHDIR_RESOURCES, glfw.FALSE)
        if not glfw.init():
            raise RuntimeError(f"GLFW initialization failed: {self.glfw_errors}")
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE if self.args.smoke_test else glfw.TRUE)
        glfw.window_hint(glfw.FOCUSED, glfw.FALSE)
        glfw.window_hint(glfw.FOCUS_ON_SHOW, glfw.FALSE)
        glfw.window_hint(glfw.FLOATING, glfw.FALSE)
        self.window = glfw.create_window(self.width, self.height, "G1 Motion Lab · Python", None, None)
        if not self.window:
            raise RuntimeError(f"OpenGL 3.3 window creation failed: {self.glfw_errors}")
        glfw.make_context_current(self.window)
        glfw.swap_interval(0 if self.args.smoke_test else 1)
        self.ctx = moderngl.create_context(require=330)
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.program = self.resource(self.ctx.program(vertex_shader=MESH_VERTEX, fragment_shader=MESH_FRAGMENT))
        self.line_program = self.resource(self.ctx.program(vertex_shader=LINE_VERTEX, fragment_shader=LINE_FRAGMENT))
        self.hud_program = self.resource(self.ctx.program(vertex_shader=HUD_VERTEX, fragment_shader=HUD_FRAGMENT))
        self.meshes = []
        for mesh in self.motion.meshes:
            buffer = self.resource(self.ctx.buffer(mesh.geometry.tobytes()))
            vao = self.resource(self.ctx.vertex_array(self.program, [(buffer, "3f 3f", "in_position", "in_normal")]))
            self.meshes.append((mesh, vao))
        grid = []
        for step in np.arange(-5, 5.01, 0.25):
            grid.extend(((step, -5, -0.008), (step, 5, -0.008), (-5, step, -0.008), (5, step, -0.008)))
        buffer = self.resource(self.ctx.buffer(np.array(grid, dtype="f4").tobytes()))
        self.grid = self.resource(self.ctx.vertex_array(self.line_program, [(buffer, "3f", "in_position")]))
        self.dynamic_buffer = self.resource(self.ctx.buffer(reserve=65536))
        self.lines = self.resource(self.ctx.vertex_array(self.line_program, [(self.dynamic_buffer, "3f", "in_position")]))
        quad = np.array([[-1, -1, 0, 1], [1, -1, 1, 1], [-1, 1, 0, 0], [1, 1, 1, 0]], dtype="f4")
        buffer = self.resource(self.ctx.buffer(quad.tobytes()))
        self.hud_quad = self.resource(self.ctx.vertex_array(self.hud_program, [(buffer, "2f 2f", "in_position", "in_uv")]))
        self.hud_program["panel"] = 0
        glfw.set_key_callback(self.window, self.on_key)
        glfw.set_mouse_button_callback(self.window, self.on_button)
        glfw.set_cursor_pos_callback(self.window, self.on_cursor)
        glfw.set_scroll_callback(self.window, self.on_scroll)
        self.check_graphics()

    def on_key(self, window, key, scancode, action, mods):
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        elif glfw.KEY_0 <= key <= glfw.KEY_3:
            self.selected = key - glfw.KEY_1
        elif key == glfw.KEY_O:
            self.overlay = not self.overlay
        elif key == glfw.KEY_SPACE:
            self.playback.toggle()
        elif key == glfw.KEY_R:
            self.playback.reset()
            self.yaw, self.pitch, self.zoom = -0.16, 0.13, 1.0
        elif key == glfw.KEY_H:
            self.help = not self.help
        elif key == glfw.KEY_S:
            self.capture_requested = Path.cwd() / "captures" / f"g1-python-{time.time_ns()}.png"

    def on_button(self, window, button, action, mods):
        if button == glfw.MOUSE_BUTTON_LEFT:
            self.dragging = action == glfw.PRESS
            self.cursor = glfw.get_cursor_pos(window)

    def on_cursor(self, window, x, y):
        if self.dragging and self.cursor:
            self.yaw -= (x - self.cursor[0]) * 0.006
            self.pitch = float(np.clip(self.pitch + (y - self.cursor[1]) * 0.003, -0.05, 1.15))
        self.cursor = (x, y)

    def on_scroll(self, window, x, y):
        self.zoom = float(np.clip(self.zoom * math.exp(-y * 0.08), 0.5, 2.5))

    def draw_lines(self, points, ink, mode=moderngl.LINES):
        if not len(points):
            return
        values = np.asarray(points, dtype="f4").reshape(-1, 3)
        if values.nbytes > self.dynamic_buffer.size:
            self.dynamic_buffer.orphan(values.nbytes)
        self.dynamic_buffer.write(values.tobytes())
        self.line_program["ink"] = ink
        self.lines.render(mode, vertices=len(values))

    def render(self, seconds):
        self.width, self.height = glfw.get_framebuffer_size(self.window)
        if self.width < 1 or self.height < 1:
            return False  # A minimized interactive window can have a zero-size framebuffer.
        self.ctx.viewport = (0, 0, self.width, self.height)
        self.ctx.screen.use()
        self.ctx.clear(0.035, 0.052, 0.067, 1.0, depth=1.0)
        self.ctx.enable(moderngl.DEPTH_TEST)
        vp, eye = camera(self.width, self.height, self.yaw, self.pitch, self.zoom, self.selected >= 0)
        self.program["view_projection"].write(matrix_bytes(vp))
        self.program["eye"] = tuple(eye)
        self.line_program["view_projection"].write(matrix_bytes(vp))
        self.line_program["ink"] = (0.10, 0.15, 0.18, 0.72)
        self.grid.render(moderngl.LINES)
        self.mesh_samples = []
        labels = []
        for index, clip in enumerate(self.motion.clips):
            if self.selected >= 0 and index != self.selected:
                continue
            positions, rotations, source = clip.sample(seconds)
            offset = clip.display_offset(index - 1 if self.selected < 0 else 0)
            # Only actual mesh draw calls count: grid, trails, source and HUD cannot pass this gate.
            query = self.ctx.query(samples=True) if self.args.smoke_test else None
            if query:
                query.__enter__()
            for mesh, vao in self.meshes:
                self.program["model"].write(matrix_bytes(transform(positions[mesh.body] + offset, rotations[mesh.body]) @ mesh.local))
                self.program["material"] = (0.16, 0.20, 0.23) if np.mean(mesh.color[:3]) < 0.28 else (0.78, 0.82, 0.83)
                vao.render(moderngl.TRIANGLES)
            if query:
                query.__exit__(None, None, None)
                self.mesh_samples.append(int(query.samples))
            # History is clipped at the start of this loop, never joined to the previous loop.
            elapsed = seconds % clip.duration
            trail_positions, _ = clip.sample_many(seconds - np.linspace(min(elapsed, 0.7), 0, 30))
            for hand in self.motion.hands:
                points = trail_positions[:, hand] + offset
                self.draw_lines(points, (0.22, 0.77, 0.83, 0.72), moderngl.LINE_STRIP)
            if self.overlay:
                self.ctx.disable(moderngl.DEPTH_TEST)
                source_lines = [source[i] + offset for child, parent in enumerate(self.motion.source_parents) if parent >= 0 for i in (int(parent), child)]
                self.draw_lines(source_lines, (0.32, 0.95, 0.84, 0.88))
                self.ctx.enable(moderngl.DEPTH_TEST)
            point = vp @ np.append(positions[0] + offset + np.array([0.0, 0.0, -positions[0, 2] - 0.16]), 1.0)
            labels.append((clip.name, (point[0] / point[3] + 1) * self.width / 2, (1 - point[1] / point[3]) * self.height / 2))
        self.draw_hud(seconds, labels)
        self.frame_count += 1
        self.check_graphics()
        return True

    def draw_hud(self, seconds, labels):
        # Pillow's bundled font avoids platform-specific font files and extra dependencies.
        scale = max(0.5, self.width / 1280)
        font = ImageFont.load_default(size=round(16 * scale))
        title_font = ImageFont.load_default(size=round(26 * scale))
        small = ImageFont.load_default(size=round(13 * scale))
        image = Image.new("RGBA", (self.width, self.height))
        draw = ImageDraw.Draw(image)
        pad = round(26 * scale)
        draw.rectangle((0, 0, self.width, round(105 * scale)), fill=(9, 13, 17, 225))
        draw.text((pad, round(19 * scale)), "G1 MOTION LAB", font=title_font, fill=(231, 241, 241))
        duration = self.motion.clips[0].duration
        selection = "A + B + C" if self.selected < 0 else "ABC"[self.selected]
        status = "PAUSED" if self.playback.paused else "PLAYBACK"
        text = f"PYTHON / OPENGL    {selection}    {seconds % duration:05.2f} / {duration:.3f} s    {status}"
        draw.text((pad, round(56 * scale)), text, font=font, fill=(107, 209, 210))
        if self.help:
            draw.text((pad, round(82 * scale)), "0 all   1 / 2 / 3 solo   O source   SPACE pause   R reset   drag orbit   scroll zoom   H help   S capture", font=small, fill=(159, 177, 186))
        footer = round(63 * scale)
        draw.rectangle((0, self.height - footer, self.width, self.height), fill=(9, 13, 17, 242))
        # Pillow's small bundled font has no em dash; draw the dash itself, not a missing-glyph box.
        label_y = self.height - footer + round(11 * scale)
        label_left, label_right = LABEL.split(" — ")
        amber = (247, 196, 125)
        draw.text((pad, label_y), label_left, font=font, fill=amber)
        dash_x = pad + draw.textlength(label_left + " ", font=font)
        draw.line((dash_x, label_y + 10 * scale, dash_x + 15 * scale, label_y + 10 * scale), fill=amber, width=max(1, round(scale)))
        draw.text((dash_x + 21 * scale, label_y), label_right, font=font, fill=amber)
        note = f"{self.motion.fps:g} Hz reference · fixed-body interpolation · mesh playback only · no robot connection"
        if not self.motion.pose_passed:
            note = "POSE QA FAILED / UNKNOWN: DIAGNOSTIC DISPLAY ONLY"
        draw.text((pad, self.height - round(25 * scale)), note, font=small,
                  fill=(249, 120, 102) if not self.motion.pose_passed else (145, 165, 176))
        for name, x, y in labels:
            if 110 * scale < y < self.height - footer - 20 * scale and 10 < x < self.width - 10:
                draw.text((x, y), name, font=font, fill=(134, 221, 218), anchor="mt")
        if self.hud_texture is None or self.hud_texture.size != image.size:
            if self.hud_texture:
                self.hud_texture.release()
            self.hud_texture = self.ctx.texture(image.size, 4)
            self.hud_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.hud_texture.write(image.tobytes())
        self.hud_texture.use(0)
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.hud_quad.render(moderngl.TRIANGLE_STRIP)

    def check_graphics(self):
        if self.glfw_errors:
            raise RuntimeError(f"GLFW errors: {self.glfw_errors}")
        error = self.ctx.error
        if error != "GL_NO_ERROR":
            raise RuntimeError(f"OpenGL error: {error}")
        if self.args.smoke_test and (glfw.get_window_attrib(self.window, glfw.VISIBLE) or glfw.get_window_attrib(self.window, glfw.FOCUSED)):
            raise RuntimeError("Smoke window became visible or focused")

    def capture(self, destination, seconds):
        if self.width < 64 or self.height < 64:
            raise RuntimeError("Framebuffer too small for a trustworthy capture")
        pixels = self.ctx.screen.read(components=3, alignment=1)
        image = Image.frombytes("RGB", (self.width, self.height), pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        values = np.asarray(image)
        content = values[int(self.height * .20):int(self.height * .86)]
        self.capture_mesh_pixels = int(np.count_nonzero(np.max(content, axis=-1) > 90))
        if self.args.smoke_test and self.capture_mesh_pixels < 150:
            raise RuntimeError("Readback contains too few bright scene pixels; HUD/grid cannot pass this capture gate")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination)
        return hashlib.sha256(image.tobytes()).hexdigest()

    def run(self):
        self.open()
        if self.args.smoke_test:
            if self.args.exercise_controls:
                self.exercise_controls()
            glfw.poll_events()
            if not self.render(self.args.time):
                raise RuntimeError("No drawable framebuffer")
            glfw.swap_buffers(self.window)
            glfw.poll_events()
            if not self.render(self.args.time):
                raise RuntimeError("No drawable framebuffer")
            if not self.mesh_samples or min(self.mesh_samples) < 150:
                raise RuntimeError(f"Insufficient actual mesh coverage: {self.mesh_samples}")
            self.check_graphics()
            digest = self.capture(self.args.capture, self.args.time) if self.args.capture else None
            report = dict(status="SMOKE_TEST_OK", time=self.args.time, clips=self.args.clip,
                          source_overlay=self.overlay, mesh_count=len(self.meshes),
                          mesh_samples=self.mesh_samples, frame_count=self.frame_count,
                          framebuffer=[self.width, self.height], visible=False, focused=False,
                          pose_status="pass" if self.motion.pose_passed else "fail_or_unknown",
                          label=LABEL, pixel_sha256=digest,
                          renderer=self.ctx.info["GL_RENDERER"], version=self.ctx.info["GL_VERSION"])
            report["controls_checked"] = self.args.exercise_controls
            if digest:
                report["readback_scene_pixels"] = self.capture_mesh_pixels
            if self.args.capture:
                Path(self.args.capture).with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report))
            return
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            seconds = self.playback.seconds()
            if self.render(seconds):
                if self.capture_requested:
                    self.capture(self.capture_requested, seconds)
                    print(f"CAPTURE_SAVED {self.capture_requested}")
                    self.capture_requested = None
                glfw.swap_buffers(self.window)
            else:
                glfw.wait_events_timeout(0.05)

    def exercise_controls(self):
        """Run real callback/render paths, preserving the requested final deterministic view."""
        initial_selected, initial_overlay = self.selected, self.overlay
        for key, expected in ((glfw.KEY_1, 0), (glfw.KEY_2, 1), (glfw.KEY_3, 2), (glfw.KEY_0, -1)):
            self.on_key(self.window, key, 0, glfw.PRESS, 0)
            if self.selected != expected or not self.render(self.args.time):
                raise RuntimeError("Clip-control render failed")
            if len(self.mesh_samples) != (3 if expected < 0 else 1) or min(self.mesh_samples) < 150:
                raise RuntimeError("Clip-control mesh coverage failed")
        self.on_key(self.window, glfw.KEY_O, 0, glfw.PRESS, 0)
        if self.overlay == initial_overlay:
            raise RuntimeError("Source-overlay control failed")
        self.on_key(self.window, glfw.KEY_SPACE, 0, glfw.PRESS, 0)
        paused = self.playback.seconds()
        if not self.playback.paused or self.playback.seconds(self.playback.started + 4) != paused:
            raise RuntimeError("Pause control failed")
        self.dragging, self.cursor = True, (20, 20)
        self.on_cursor(self.window, 70, 35)
        self.on_scroll(self.window, 0, 1)
        if self.yaw == -0.16 or self.zoom == 1.0:
            raise RuntimeError("Orbit/zoom controls failed")
        self.on_key(self.window, glfw.KEY_R, 0, glfw.PRESS, 0)
        if (self.yaw, self.pitch, self.zoom, self.playback.seconds()) != (-0.16, 0.13, 1.0, 0.0):
            raise RuntimeError("Reset control failed")
        self.on_key(self.window, glfw.KEY_H, 0, glfw.PRESS, 0)
        self.render(self.args.time)  # Safety label remains outside the optional help branch.
        glfw.set_window_size(self.window, 960, 720)
        glfw.poll_events()
        if not self.render(self.args.time):
            raise RuntimeError("Resize render failed")
        glfw.set_window_size(self.window, self.args.width, self.args.height)
        glfw.poll_events()
        self.selected, self.overlay, self.help, self.dragging = initial_selected, initial_overlay, True, False
        self.playback = Playback(self.args.time)

    def close(self):
        if self.hud_texture:
            self.hud_texture.release()
        for resource in reversed(self.resources):
            resource.release()
        if self.ctx:
            self.ctx.release()
        if self.window:
            glfw.destroy_window(self.window)
        glfw.terminate()


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Canonical reference directory (not copied into this example)")
    parser.add_argument("--smoke-test", action="store_true", help="Render hidden/unfocused and exit with fail-closed mesh/GL checks")
    parser.add_argument("--time", type=float, default=0.0, help="Initial/deterministic playback time in seconds")
    parser.add_argument("--capture", type=Path, help="Absolute PNG path; implies --smoke-test; adds a JSON evidence sidecar")
    parser.add_argument("--clip", choices=["all", "A", "B", "C"], default="all")
    parser.add_argument("--source-overlay", action="store_true")
    parser.add_argument("--exercise-controls", action="store_true", help="In hidden smoke mode also verify solo/all, pause/reset, orbit/zoom, help and resize paths")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    args = parser.parse_args(argv)
    if not math.isfinite(args.time) or args.time < 0:
        parser.error("--time must be finite and nonnegative")
    if not 320 <= args.width <= 4096 or not 240 <= args.height <= 4096:
        parser.error("window dimensions must be 320..4096 by 240..4096")
    if args.capture:
        if not args.capture.is_absolute() or args.capture.suffix.lower() != ".png":
            parser.error("--capture requires an absolute .png path")
        args.smoke_test = True
    if args.exercise_controls and not args.smoke_test:
        parser.error("--exercise-controls requires --smoke-test or --capture")
    return args


def main(argv=None):
    viewer = None
    try:
        args = arguments(argv)
        motion = Motion.load(args.data)
        viewer = Viewer(motion, args)
        viewer.run()
        return 0
    except DataError as exc:
        print(f"G1_DATA_ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"G1_GRAPHICS_ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if viewer:
            viewer.close()


if __name__ == "__main__":
    raise SystemExit(main())
