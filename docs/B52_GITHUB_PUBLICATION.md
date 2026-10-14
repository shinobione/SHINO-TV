# B5.2 GitHub publication — source-closure CI correction

Owner archive review completed as **READY_FOR_GITHUB_REVIEW**, software only.
The40 worktree files matched the reviewed archive before the two publication
commits. Only active summaries additionally recorded the new publication mandate.
Draft [PR48](https://github.com/shinobione/SHINO-TV/pull/48) targets frozen B5.1
244334edac07701dc25b5ffc494715152ae1bfa5 / PR47, not main.

## Demonstrated CI problem

Initial published HEAD a60a5ef4845b0bad68436478685107593b60de44 triggered9 runs:
3 completed successfully and6 failed. The failures were historical source
comparisons, not clock test failures:

- Mount-stack/Phase O rejected the reviewed SceneEngine as source drift.
- Signed/StageA/normal HTTP audit paths inherited those failures.
- The two old Wi-Fi resource audits requested ClockFoundation from a checkpoint
  predating that file, so git show failed before their resource verdict.
- Core unit CI reported5 source-audit errors for that same SceneEngine mismatch.

The failure is independently reproduced by source_audit() and Phase O
source_gate(), with no firmware build, secret or device access.

## Bounded correction and guarantees

b52_source_compat.py proves one exact reviewed SceneEngine overlay using SHA-256
of LF-normalized source, seven exact inverse diff blocks, and the complete
immutable predecessor digest. Any unreviewed scene mutation fails closed. The
new ClockFoundation header has a separate exact SHA-256 pin; the four new PC
files and header have exact Git blob pins in signed/StageA source inventories.
All other historical files still undergo their original comparisons. Unknown
added firmware paths fail, and the firmware-set test requires precisely the
historical113 paths plus the one separately pinned header.

Phase O reports PINNED_B52_PREDECESSOR_PROJECTION rather than raw current-file
identity. Signed-source output no longer claims current installed sources are
unchanged when the reviewed scene overlay is present. The two Wi-Fi resource
reports now carry an explicit historical projection receipt. Phase K validates
this precise provenance and the separate added-header pin. No workflow is
skipped or disabled by the correction.

No historical source-pin JSON, physical writer, runtime clock source, normal
transport, memory floor or firmware layout changed. The reviewed18 runtime/
client/test/lab/generator files and all five captures remain byte-identical to
the owner archive. Historical BIN/RAM numbers in B52_CLOCK_FRESHNESS_FIX.md remain
retained evidence, not a new firmware measurement. No firmware rebuild was
performed locally during publication.

## Targeted validation actually executed

-6 compatibility tests PASS, including exact inverse reconstruction, mutation
  rejection, added-header drift, exact Wi-Fi historical closure and physical HOLD.
-12 relevant historical source/readiness tests PASS.
-23 PC clock tests and3 public generator guards PASS, freshly rerun.
-Signed and StageA source-gate APIs PASS against installed pinned Core source.
-git diff --check PASS for the CI correction. The original reviewed additions
 retain14 EOF blank-line findings, unchanged and already disclosed in the PR.

Actual commands:

```powershell
python -X utf8 -m unittest discover -s tools -p 'test_b52_source_compat.py' -q
$env:PYTHONPATH='tools'
python -X utf8 -m unittest test_m9_mount_stack.SourceTests test_m9_phase_o.PhaseOTests.test_exact_active_binding_source_and_firmware_identity test_m9_phase_o.PhaseOTests.test_print_only_packet_and_normal_gates_no_boot_authority test_m9_phase_n.SourceTests test_m9_normal_readiness.ReadinessTests -q
python -X utf8 -m unittest discover -s companion -p 'test_clock*.py' -q
python -X utf8 -m unittest discover -s tools -p 'test_shino_b52_clock_build.py' -q
git diff --check
```

Source-gate APIs invoked from a Python here-string with tools on sys.path:

```python
from m9_signed_ota_runner import source_gate
from m9_stagea_source_gate import run
source_gate()
run()
```

One initial local invocation of the full5-case mount-stack module passed4 and
failed its compiled workspace fixture because g++/clang++ was unavailable on
PATH. No guard or compiler test was removed; the relevant four SourceTests were
rerun successfully above, and Linux CI retains the compiled case. No broad
historical suite was rerun locally. Retained B5.2 MSVC ASan proofs were not
repeated; B5.2 UBSan remains NOT_RUN, and hardware qualification remains HOLD.

Exact final-head workflow conclusions are reported on PR48 after the correction
push. This document does not substitute old-head evidence for that verification.
Installed B5.1, its frozen reference, the principal worktree and all private
artifacts remain untouched. No physical network/device operation, private build,
OTA, flash, RTC write, reboot, provisioning, Wi-Fi change or merge.
