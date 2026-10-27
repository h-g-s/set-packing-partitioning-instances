# Nauty-free rerun provenance

This is a fresh experiment, not a resumption or selective repair of the first
round. The same 47 models, seeds 6401/6402, 1,800-second limit, 16 jobs and three
repeated OFF controls give **191 planned runs**. Both arms use the same frozen
executable. No favorable outcome is assumed.

## Solver source

Upstream baseline: `coin-or/Cbc@97ca70c7dd1396e3aa66ff6ac0c4860b5fb6f12d`
(master, SppGrasp OFF by default).

Local reporting-fix commit:
`d76c74fc5a77f4d31b1134cfa7e90b466c92949e`.
This commit is local, not an upstream release. Its complete diff from the
upstream baseline is [progress-csv-fix.patch](progress-csv-fix.patch).
Apply that patch to the baseline to reproduce the source; do not substitute
upstream next, which contains unrelated heuristic changes.

Previously CSV initialization/finalization on an early initial-LP return
required a native pre-LP incumbent. The fix finalizes the progress history for
every such return, while keeping incumbent-vector transfer conditional.
It does not fabricate a primal/dual bound, change a heuristic or alter search.

Patch SHA-256:
`e9792a558f6fdadb5de293191fc7d5ed25dd83fadd042ba8f881990a4f8db2f0`.

All five source commits, input hashes, executable hashes, runtime libraries and
exact run commands are in [manifest.json](manifest.json). Tracked source changes
were rejected during preparation. The regular workspace's unrelated edits were
not used.

## Build

The clean dependency stack was configured and installed in dependency order:

```sh
./config --opt --no-nauty --install --prefix=/absolute/path/to/nonauty-install
```

After applying the reporting patch, rebuild/install Cbc against that same
prefix. `CBC_HAS_NAUTY` is undefined in the generated configuration and `ldd`
shows no Nauty library. Both arms therefore exclude symmetry search through
Nauty; this is a build configuration change, not a solver-default change.

Frozen CBC SHA-256:
`b2cb594e2f65f2423f10942134bd3d1d94fed5274e6430a393c3d073bef320d1`.

The independent validator was rebuilt against this installation's `cbc`
pkg-config package. Its SHA-256 is
`ec8dfd95f8cef78c92da4731cc72310a4bee7a20f2daaedf50cf100045184d01`.

## Preflight validation

The focused zero-second initial-LP regression fails on the original executable
because the CSV does not exist. With the fix, SppGrasp OFF, native completion
explicitly disabled and default native completion all emit start/final events,
retain an unknown incumbent, and integrate to exactly **PDI = 2**.

The complete progress-history, native-pre-LP and validator objective-offset
selftests passed. A 35-second end-to-end OFF/ON smoke test on `t1717`, `ivu06`
and `ivu06-big` passed **all six runs**, with independently validated solutions
and complete CSV histories. These preflight runs are not part of the 30-minute
results and provide no whole-collection performance conclusion.

## Preserved first round

The [first report](../2026-10-26-sppgrasp-1800s/REPORT.md) remains incomplete.
Both original `t1717` ON cores show deep Nauty recursion and stack exhaustion
through `CbcNauty::computeAuto` / `CbcSymmetry::setupSymmetry`, not a SppGrasp
stack frame. Four OFF runs on `ivu06`/`ivu06-big` stopped in the initial LP
without progress CSVs. No missing history was synthesized and no failed run
was silently dropped. This rerun keeps those findings separate.
