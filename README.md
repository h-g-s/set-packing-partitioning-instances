# SPP-dominant MIP instances

A research collection combining **MIPLIB 2017** models with additional real
application models collected over the years. The collection contains **47**
instances: **29 strictly pure binary set packing/partitioning models** and
**18 separately labeled supplemental application models** (RMP) with additional
rows. It is not a claim that every supplemental row is packing or partitioning.
Here **SPP-dominant** means at least 90% of the original rows are set packing
or set partitioning; **pure SPP** means 100%. Counts use the exact positive-unit
row definition below, not rounded feature percentages.

See [instance characteristics](CHARACTERISTICS.md) for model dimensions,
nonzeros, row counts and native slack coverage; [instances.tsv](instances.tsv)
provides source attribution, cohort labels and SHA-256 checksums.
[metadata/all-features.tsv](metadata/all-features.tsv) contains fresh features
for all 403 screened source models, computed by COIN-OR's `OsiFeatures`.
No solver-performance result was used to select or exclude an instance.
All models are distributed unchanged as compressed MPS files in `instances/`.

## CBC SppGrasp experiment

The primary comparison covers **the whole 47-instance collection**, including
air03 and models that may not benefit. It compares clean upstream CBC's current
disabled setting with explicit `-sppGrasp on` in the **same frozen binary**.
No solver defaults, heuristic budgets, FPump settings or search ordering are
changed. Internal trigger-policy design is outside the scope of this report.

Each model receives **1,800 seconds of elapsed solve time**, with two matched
seeds (6401, 6402) and serial CBC (`-threads 0`). Sixteen independent processes
use the machine's 16 physical cores; BLAS/OpenMP threads are limited to one.
Off runs precede on runs; repeated off controls on air03, ds and rmp03 measure
timing/load drift. This is a selected structural collection, not a random
population or independent holdout from earlier SppGrasp development.

The report includes proven-optimal counts, missing-incumbent counts, terminal
gaps, elapsed times, time to first incumbent and **primal-dual integral (PDI)**.
PDI is the primary metric: lower is better. Both gains and regressions are
retained. A successful result is not assumed in advance.

PDI uses the complete progress CSV clock, including original-model incumbents
and the global final event, not approximate console timestamps. With horizon
`T = 1800`, gap is 2 without an incumbent, 1 with an incumbent but no usable
dual bound (or opposite-sign bounds), otherwise
`|primal-dual| / max(|primal|, |dual|)`. A proof closes the gap at its actual
timestamp; interrupted runs hold their last gap to T. PDI is
`integral(gap(t), 0, T) / T`. No-incumbent gaps are reported separately, not
misrepresented as finite conventional MIP gaps.

Saved vectors are independently checked for bounds, integrality, row
feasibility and objective consistency using CBC's `cbc_validate_sol`.
Known reference objectives are also used to cross-check proof claims.
Errors, hard timeouts, missing final events and failed validations are explicit;
they cannot silently disappear from a favorable average.

See [the experiment protocol](EXPERIMENT.md) and the report under `results/`
when complete. While the study is running, there is **no aggregate outcome
claim**. Raw logs, solutions and progress histories remain in the experiment
directory and can be archived separately without inflating Git history.

Current study: [30-minute paired benchmark](results/2026-10-26-sppgrasp-1800s/STATUS.md).
The launcher publishes the final validated tables and figures to that directory,
and attaches raw evidence and frozen binaries to a GitHub release.

## Reproduction

Build the clean dependency stack with `cbc-workspace`'s `config --opt --install`,
using the commits and flags recorded in the experiment manifest. Compile
`tools/extract_features.cpp` against the installed `cbc` and `osi-clp`
pkg-config packages. `tools/curate.py --help` describes fresh extraction.

`tools/run_study.py --help` runs and validates a frozen paired benchmark.
`tools/report.py --help` regenerates whole-collection statistics and figures
from its raw artifacts. GNU parallel dispatches independent solves.
Reporting requires Python, NumPy and matplotlib; the PDI computation is vendored
unchanged from CBC with provenance in `tools/UPSTREAM.md`.

## Sources, citation and licensing

Original application models contributed by the collection maintainer, new
scripts and documentation are provided under **EPL-2.0** (see [LICENSE](LICENSE)).
MIPLIB models retain their **original authorship and terms**; this repository
does not relicense third-party models as EPL-2.0. Each model's attribution is
listed in `instances.tsv`. Source details unavailable for contributed models
are left unspecified rather than invented.

MIPLIB 2017: https://miplib.zib.de/ and its
[download page](https://miplib.zib.de/download.html).
Please cite:

> Gleixner et al. (2021). *MIPLIB 2017: Data-Driven Compilation of the 6th
> Mixed-Integer Programming Library*. Mathematical Programming Computation.
> https://doi.org/10.1007/s12532-020-00194-3

Reference objectives use the official MIPLIB solution file v37 and the local
collection's BKS table. A best-known value is **not** necessarily a proven optimum.
Models and references are supplied without warranty.
