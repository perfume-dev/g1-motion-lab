"""Copyright (c) 2026 Daito Manabe. MIT."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prepare_data', ROOT / 'scripts/prepare-data.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PackageTests(unittest.TestCase):
    def test_retarget_source_snapshot_matches_actual_module_bytes(self):
        kit = ROOT / 'tools/g1-retarget'
        snapshot = json.loads((kit / 'SOURCE_SNAPSHOT.json').read_text())
        self.assertEqual(len(snapshot['files_sha256']), 8)
        for relative, expected in snapshot['files_sha256'].items():
            path = (kit / relative).resolve()
            self.assertTrue(path.is_relative_to(kit.resolve()))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected, relative)

    def test_actual_canonical_package_preserves_full_accepted_references(self):
        self.assertEqual(len(prepare.verify(ROOT)), 8)

    def sources(self, root):
        source = root / 'data/reference'
        source.mkdir(parents=True)
        for name in prepare.REFERENCE_FILES:
            (source / name).write_bytes(b'fixture bytes')

    def test_stage_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.sources(root)
            self.assertEqual(prepare.stage(root, ['processing']), 5)
            self.assertEqual(prepare.stage(root, ['processing']), 0)

    def test_edited_destination_aborts_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.sources(root)
            target = root / prepare.VIEWERS['processing']
            target.mkdir(parents=True)
            (target / 'MODEL-LICENSE').write_bytes(b'user edit')
            with self.assertRaisesRegex(ValueError, 'overwrite edited'):
                prepare.stage(root, ['processing'])
            self.assertEqual(list(target.iterdir()), [target / 'MODEL-LICENSE'])
            self.assertEqual((target / 'MODEL-LICENSE').read_bytes(), b'user edit')

    def test_external_symlink_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            self.sources(root)
            target = root / prepare.VIEWERS['processing']
            target.parent.mkdir(parents=True)
            target.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'outside'):
                prepare.stage(root, ['processing'])
            self.assertEqual(list(Path(outside).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
