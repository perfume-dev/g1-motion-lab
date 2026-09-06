#!/usr/bin/env bash
# Copyright (c) 2026 Daito Manabe
# SPDX-License-Identifier: MIT; see ../LICENSE
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 /path/to/Processing /path/to/test-output" >&2
  exit 2
fi
processing_bin=$1
mkdir -p "$2"
test_output=$(cd "$2" && pwd)
repo_root=$(cd "$(dirname "$0")/.." && pwd)
sketch_root="$repo_root/examples/processing/g1_motion_lab"
test_root="$repo_root/tests/processing"

python3 -B "$repo_root/scripts/prepare-data.py" --viewer processing
python3 -B -m unittest discover -s "$test_root" -p 'test_*.py'
for filename in g1-motion.json g1-model.json pose_retarget_qa.json provenance.json MODEL-LICENSE; do
  if ! cmp -s "$repo_root/data/reference/$filename" "$sketch_root/data/$filename"; then
    echo "Missing or stale Processing data: run python3 scripts/prepare-data.py --viewer processing from the repository root" >&2
    exit 1
  fi
done
if [[ $(uname -s) == Darwin ]]; then
  export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:+$JAVA_TOOL_OPTIONS }-Dapple.awt.UIElement=true"
fi

run_processing() {
  # Bound both the launcher and its child JVM, without touching other applications.
  perl -MPOSIX -e '
    my $limit = shift @ARGV;
    my $child = fork();
    defined $child or die "Cannot fork: $!";
    if (!$child) { POSIX::setsid(); exec @ARGV; die "Cannot launch: $!"; }
    my $status;
    eval {
      local $SIG{ALRM} = sub { die "Processing timed out\n"; };
      alarm $limit;
      waitpid($child, 0);
      $status = $?;
      alarm 0;
    };
    if ($@) {
      warn $@;
      kill "TERM", -$child;
      sleep 1;
      kill "KILL", -$child;
      waitpid($child, 0);
      exit 124;
    }
    exit(($status & 127) ? 128 + ($status & 127) : ($status >> 8));
  ' 60 "$processing_bin" "$@"
}

first_frame=
previous_frame=
for seconds in 8 16 14.3 14.3125; do
  run_dir=$(mktemp -d "$test_output/g1-$seconds.XXXXXX")
  run_processing cli --sketch="$sketch_root" --output="$run_dir/build" \
    --run --smoke-test --time="$seconds" --capture="$run_dir/frame.png" 2>&1 | tee "$run_dir/runtime.log"
  grep -q 'SMOKE_TEST_OK sketch=g1_motion_lab' "$run_dir/runtime.log"
  grep -q 'scope=rendering-only' "$run_dir/runtime.log"
  test -s "$run_dir/frame.png"
  if [[ -n "$previous_frame" ]] && cmp -s "$previous_frame" "$run_dir/frame.png"; then
    echo "G1 did not change between motion timestamps" >&2
    exit 1
  fi
  previous_frame="$run_dir/frame.png"
  if [[ "$seconds" == 8 ]]; then first_frame="$run_dir/frame.png"; fi
done

# Render success never substitutes for the separate pose/physics acceptance gates.
overlay_dir=$(mktemp -d "$test_output/g1-source-overlay.XXXXXX")
run_processing cli --sketch="$sketch_root" --output="$overlay_dir/build" \
  --run --smoke-test --time=8 --source-overlay --capture="$overlay_dir/frame.png" 2>&1 | tee "$overlay_dir/runtime.log"
grep -q 'SMOKE_TEST_OK sketch=g1_motion_lab' "$overlay_dir/runtime.log"
grep -q 'sourceOverlay=true' "$overlay_dir/runtime.log"
grep -q 'scope=rendering-only' "$overlay_dir/runtime.log"
test -s "$overlay_dir/frame.png"
if cmp -s "$first_frame" "$overlay_dir/frame.png"; then
  echo "G1 source overlay did not change the rendered frame" >&2
  exit 1
fi

# Corrupt only new disposable sketch copies; canonical/prepared data remain unchanged.
for failure in missing-motion missing-model schema quaternion index frame-size validation-label \
  model-schema fractional-schema fractional-parent fractional-body fractional-index overflow-index \
  missing-offsets offset-shape offset-nonfinite offset-mismatch non-topological-parent multiple-roots root-self-parent; do
  negative_dir=$(mktemp -d "$test_output/g1-data-$failure.XXXXXX")
  python3 -B "$test_root/make_negative_fixture.py" "$sketch_root" "$negative_dir/g1_motion_lab" "$failure"
  if run_processing cli --sketch="$negative_dir/g1_motion_lab" --output="$negative_dir/build" \
    --run --smoke-test --capture="$negative_dir/frame.png" > "$negative_dir/runtime.log" 2>&1; then
    # Processing can return zero for a failed sketch: require explicit failure evidence.
    echo "Launcher returned zero; checking explicit G1 data failure evidence."
  fi
  cat "$negative_dir/runtime.log"
  grep -a -q 'G1_DATA_ERROR:' "$negative_dir/runtime.log"
  if grep -a -q 'Processing timed out' "$negative_dir/runtime.log"; then exit 1; fi
  if grep -q 'SMOKE_TEST_OK' "$negative_dir/runtime.log" || [[ -e "$negative_dir/frame.png" ]]; then
    echo "Invalid G1 data ($failure) incorrectly passed or wrote a capture" >&2
    exit 1
  fi
done

for filename in g1-motion.json g1-model.json pose_retarget_qa.json provenance.json MODEL-LICENSE; do
  cmp "$repo_root/data/reference/$filename" "$sketch_root/data/$filename"
done
echo "PROCESSING_SUITE_OK captures=5 invalidDataRejected=20 scope=rendering-only"
