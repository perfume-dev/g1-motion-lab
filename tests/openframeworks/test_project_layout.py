"""Copyright (c) 2026 Daito Manabe. MIT; packaging regression checks only."""
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "examples/openframeworks"
PROJECT = APP / "example-g1-motion-lab.xcodeproj"


class OpenFrameworksLayoutTests(unittest.TestCase):
    def test_no_old_repository_or_addon_dependency(self):
        source = "\n".join(path.read_text() for path in (APP / "src").glob("*"))
        self.assertNotIn("ofxBvh", source)
        self.assertNotIn("ExampleRuntime", source)
        self.assertNotIn("MotionPlayback", source)
        self.assertIn('#include "Runtime.h"', (APP / "src/ofApp.h").read_text())
        addons = [line for line in (APP / "addons.make").read_text().splitlines()
                  if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(addons, [])

    def test_standard_depth_and_stable_binary_name(self):
        config = (APP / "config.make").read_text()
        self.assertRegex(config, r"(?m)^OF_ROOT\s*\?=\s*\.\./\.\./\.\./\.\./\.\.\s*$")
        self.assertRegex(config, r"(?m)^APPNAME\s*=\s*example-g1-motion-lab\s*$")
        xcode = (APP / "Project.xcconfig").read_text()
        self.assertIn("OF_PATH = ../../../../..\n", xcode)
        self.assertIn('#include "../../../../../libs/openFrameworksCompiled/project/osx/CoreOF.xcconfig"', xcode)

    def test_xcode_references_only_local_application_sources(self):
        project_text = (PROJECT / "project.pbxproj").read_text()
        self.assertNotIn("ofxBvh", project_text)
        objects = json.loads(project_text)["objects"]
        compiled = []
        for item in objects.values():
            if item["isa"] == "PBXSourcesBuildPhase":
                for build_id in item["files"]:
                    compiled.append(objects[objects[build_id]["fileRef"]]["path"])
        self.assertEqual(sorted(compiled), ["src/main.cpp", "src/ofApp.cpp"])
        for item in objects.values():
            if item["isa"] == "PBXFileReference" and item.get("sourceTree") == "SOURCE_ROOT":
                path = item["path"]
                if path.startswith("../"):
                    # OF is external and need not be installed for this packaging test.
                    self.assertIn(path, {"../../../../../libs/openFrameworks", "../../../../../addons"})
                else:
                    self.assertTrue((APP / path).exists(), path)
        self.assertTrue(any(item.get("path") == "src/Runtime.h" for item in objects.values()))
        for scheme in (PROJECT / "xcshareddata/xcschemes").glob("*.xcscheme"):
            for reference in ET.parse(scheme).iter("BuildableReference"):
                self.assertEqual(objects[reference.attrib["BlueprintIdentifier"]]["isa"], "PBXNativeTarget")

    def test_staging_and_bounded_capture_contract(self):
        build = (ROOT / "scripts/build-openframeworks.sh").read_text()
        self.assertIn('prepare-data.py" --viewer openframeworks', build)
        script = (ROOT / "scripts/verify-openframeworks.sh").read_text()
        capture_frames = re.findall(r'^\s*render_app .*--capture-frame=(\d+)$', script, re.MULTILINE)
        self.assertEqual(capture_frames, ["480", "960", "960", "860"])
        self.assertIn("sleep 240", script)
        self.assertIn("timeout=90, check=False", script)
        self.assertEqual(len(re.findall(r'^        \("[a-z-]+", ', script, re.MULTILINE)), 22)
        self.assertIn("symlinks=False", script)


if __name__ == "__main__":
    unittest.main()
