# Prepared: 30-minute paired benchmark

47 instances, two matched seeds, off/on in the same clean upstream binary:
188 primary runs plus three repeated off controls.

All five COIN-OR projects were built from clean committed sources. The
progress-clock and objective-offset selftests passed. The full
solve/export/validate/analyze/plot pipeline passed a two-model smoke test;
those short smoke results are not benchmark evidence.

The long study will run locally with 16 concurrent serial solves and a
1,800-second elapsed limit per solve. See [manifest.json](manifest.json)
for exact commands, source revisions, input/binary hashes and machine details.

**No whole-collection results are available yet.** The final report, figures
and raw-evidence release are published automatically after the study ends.
Failures or incomplete runs will be explicitly reported.
