#!/usr/bin/env python3
"""Verify canonical recordings/references and stage disposable viewer copies.

Copyright (c) 2026 Daito Manabe. MIT; code only, not performance/model assets.
No downloads, retargeting, physics, network services or hardware commands.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

REFERENCE_FILES = ('g1-motion.json', 'g1-model.json', 'pose_retarget_qa.json',
                   'provenance.json', 'MODEL-LICENSE')
EXPECTED_FILES = {f'reference/{name}' for name in REFERENCE_FILES} | {
    f'source/{letter}_test.bvh' for letter in 'ABC'}
VIEWERS = {'openframeworks': 'examples/openframeworks/bin/data',
           'processing': 'examples/processing/g1_motion_lab/data'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    def invalid(value):
        raise ValueError(f'Non-finite JSON constant: {value}')
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=invalid)


def verify(root):
    data = root / 'data'
    manifest = read_json(data / 'manifest.json')
    if type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1:
        raise ValueError('Unsupported data manifest')
    files = manifest.get('files', [])
    if len(files) != len(EXPECTED_FILES) or {item.get('path') for item in files} != EXPECTED_FILES:
        raise ValueError('Manifest must contain exactly the canonical eight assets')
    hashes = {}
    for item in files:
        path = data / item['path']
        if not path.resolve().is_relative_to(data.resolve()):
            raise ValueError('Canonical asset escapes data directory')
        if type(item.get('bytes')) is not int or item['bytes'] < 1:
            raise ValueError('Invalid byte count')
        actual = digest(path)
        if path.stat().st_size != item['bytes'] or actual != item['sha256']:
            raise ValueError('Canonical asset differs from manifest: ' + item['path'])
        hashes[item['path']] = actual
    qa = read_json(data / 'reference/pose_retarget_qa.json')
    motion = read_json(data / 'reference/g1-motion.json')
    if qa.get('status') != 'pass' or qa.get('physical_tracking_validated') is not False:
        raise ValueError('Expected accepted kinematic QA, never physical approval')
    if set(qa.get('clips', {})) != set('ABC') or motion.get('fps') != 40:
        raise ValueError('Expected original-rate A/B/C references')
    if motion.get('validation', {}).get('pose_status') != 'pass':
        raise ValueError('Motion is not the accepted reference')
    clips = motion.get('clips', [])
    if len(clips) != 3 or {c.get('name') for c in clips} != set('ABC'):
        raise ValueError('Missing or duplicate dance clip')
    for clip in clips:
        report = qa['clips'][clip['name']]
        if len(clip['frames']) != 1299 or report.get('frames') != 1299 or report.get('fps') != 40:
            raise ValueError('Partial or resampled dance reference')
        if report.get('status') != 'pass' or report.get('failed_gates') != []:
            raise ValueError('Pose gates did not pass')
        if report['source_sha256'] != hashes[f"source/{clip['name']}_test.bvh"]:
            raise ValueError('QA source does not match bundled BVH')
    provenance = read_json(data / 'reference/provenance.json')
    for name, expected in provenance['files_sha256'].items():
        if name not in REFERENCE_FILES or hashes[f'reference/{name}'] != expected:
            raise ValueError('Derived package provenance mismatch')
    return hashes


def stage(root, viewers):
    """Preflight every destination before writing; never overwrite edited data."""
    pairs = [(root / 'data/reference' / name, root / VIEWERS[viewer] / name)
             for viewer in viewers for name in REFERENCE_FILES]
    for source, target in pairs:
        if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
            raise ValueError('Refusing a symlink or destination outside this repository: ' + str(target))
        if target.exists() and (not target.is_file() or digest(target) != digest(source)):
            raise ValueError('Refusing to overwrite edited viewer data; move it aside first: ' + str(target))
    copied = 0
    for source, target in pairs:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied += 1
    return copied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--viewer', choices=[*VIEWERS, 'all'], default='all')
    parser.add_argument('--check', action='store_true', help='Verify canonical data only; write nothing')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    verify(root)
    count = 0 if args.check else stage(root, list(VIEWERS) if args.viewer == 'all' else [args.viewer])
    print(json.dumps({'status': 'pass', 'canonical_assets': 8, 'clips': 3,
                      'frames_per_clip': 1299, 'fps': 40, 'copied_files': count,
                      'scope': 'Preserved kinematic reference; NOT physical robot control'}))


if __name__ == '__main__':
    main()
