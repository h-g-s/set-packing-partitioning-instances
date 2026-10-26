# Preregistered paired comparison

The principal outcome is mean PDI on **all 47 models**, with equal weight per
model and matched seed. Whole-set proven-optimal count, terminal gap, solve time,
missing incumbents and time to first incumbent accompany it. Cohort/family
breakdowns are descriptive secondary results, not replacements for the full set.

The clean CBC source is `coin-or/Cbc@97ca70c7dd1396e3aa66ff6ac0c4860b5fb6f12d`,
including the off-default change `65e778e18abadcd13a84ad8a900969b08cbc2450`.
Both arms use the identical executable and dependency installation. Full source
commits, compiler, binary checksums, CPU and flags are in `manifest.json`.
The normal working tree and its unrelated edits are not used.

For each seed in 6401, 6402, run every model with off, then every model with on:

```sh
cbc model.mps.gz -timeMode elapsed -threads 0 -sec 1800 \
  -randomSeed SEED -randomCbcSeed SEED -sppGrasp off \
  -progressCsv run.progress.csv -solve -solu run.sol -quit
```

Replace only `off` by `on` in the treatment arm. No explicit FPump override,
artificial slacks, minimum slack fraction, workload retuning or forced applicability
is introduced. Selection is structural and frozen before the performance runs.
The raw-model eligibility table does not predict applicability after preprocessing.
No solver implementation or parameter naming changes are part of this experiment.

GNU parallel uses 16 jobs on 16 physical cores. Each process has one BLAS/OpenMP
thread. An external timeout at 2,160 seconds guards solver overruns and is
reported as an error, never a successful capped solve. Inputs are SHA-256
verified before execution; task manifests contain exact commands.

After each run, validate the exported solution independently. A claimed optimum
must not be worse than a known feasible BKS; a known-proven objective must match.
An unexpected infeasibility claim on a model with a feasible BKS is a failure.
Timed-out runs without a real incumbent are not validated as integer vectors.
CSV events must be finite and chronological and contain a positive final
timestamp. For on runs on models with an original-model SppGrasp incumbent,
the acceptance event must be present. Progress-history/objective-offset selftests
are run before the benchmark to guard the known historical PDI clock omissions.

Repeat off controls for air03, ds and rmp03 with seed 6401 after the paired
phases. Report duplicate-control PDI variation; do not mix controls into the
primary paired averages. Six duplicate/paired observations are insufficient
to establish a universal noise bound.

Only complete pairs with validated metrics enter paired summaries, and every
excluded/incomplete/failed run is enumerated. The report is prominently marked
incomplete if any planned run is missing or erroneous. Never present a partial
average as a completed whole-collection result.

Report ordinary finite final relative gaps only on a **common paired subset**
with a genuine incumbent and usable bound in both arms, with that denominator.
Also report missing incumbents and unknown-bound counts, plus the all-run
normalized terminal gap penalty (same convention as PDI). Mean runtime includes
all valid runs, not just easy solved models; timeout-capped and actual elapsed
times are distinguished. Count only independently validated optimal solutions.

Plot the full-set mean gap trajectory and cumulative PDI, a paired per-instance
PDI change chart (including regressions), and time-to-first-incumbent coverage.
Bootstrap paired mean PDI differences by **instance**, not by seed, so repeated
seeds are not treated as independent problems. Report individual proof gains and
losses as well as totals. Air03 remains visible even if it favors off.

This comparison measures the combined effect of enabling SppGrasp and any
existing integration interactions it triggers (including FPump policy and
native pre-LP completion); it does not isolate randomized LNS alone. Running
off before on can introduce temporal load bias; duplicate controls quantify
some but not all of that risk.
