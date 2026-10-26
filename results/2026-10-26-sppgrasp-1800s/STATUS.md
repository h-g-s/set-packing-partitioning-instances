# Running: 30-minute paired benchmark

47 instances, two matched seeds, off/on in the same clean upstream binary:
188 primary runs plus three repeated off controls.

All five COIN-OR projects were built from clean committed sources. The
progress-clock and objective-offset selftests passed. The full
solve/export/validate/analyze/plot pipeline passed a two-model smoke test;
those short smoke results are not benchmark evidence.

The long study has started locally with 16 concurrent serial solves and a
1,800-second elapsed limit per solve. The first off/6401 runs for air03 and
eilB76 completed and validated; 16 solver workers were verified active.
The detached launcher survives closing this terminal.
See [manifest.json](manifest.json)
for exact commands, source revisions, input/binary hashes and machine details.

**No whole-collection results are available yet.** The final report, figures
and raw-evidence release are published automatically after the study ends.
Failures or incomplete runs will be explicitly reported.
