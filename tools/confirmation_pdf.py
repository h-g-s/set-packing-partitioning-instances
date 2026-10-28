#!/usr/bin/env python3
"""Generate a trace-checked, three-arm SppGrasp report and printable PDF source."""

import argparse
import csv
import json
import statistics
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import cbc_pdi
import matplotlib.pyplot as plt
import numpy as np
from report import cumulative_curve

ARMS = ("off", "on", "work500-keep-pump")
LABELS = ("OFF", "Unchanged ON", "500M + FPump retained")
COLORS = ("#b55d23", "#687987", "#087e8b")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    evidence, out = args.evidence.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((evidence / "manifest.json").read_text())
    summary = json.loads((evidence / "confirmation-summary.json").read_text())
    assert summary["complete"] and len(manifest["tasks"]) == 564
    records = {}
    for task in manifest["tasks"]:
        base = evidence / "raw" / task["arm"] / str(task["seed"]) / task["instance"]
        record = json.loads(Path(str(base) + ".result.json").read_text())
        assert record["valid"], str(base)
        records[task["arm"], task["seed"], task["instance"]] = record
    names = [row["instance"] for row in manifest["inputs"]]
    seeds = manifest["seeds"]
    horizon = manifest["sec"]
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False,
    })
    grid = np.unique(np.r_[0, np.geomspace(.001, horizon, 1800),
                           np.linspace(0, horizon, 1800)])
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    deltas = []
    model_rows = []
    for name in names:
        selected = [[records[arm, seed, name]["metrics"] for seed in seeds]
                    for arm in ARMS]
        pdis = [statistics.mean(m["pdi"] for m in arm) for arm in selected]
        optima = [sum(m["optimal_within_horizon"] for m in arm) for arm in selected]
        deltas.append(pdis[2] - pdis[0])
        model_rows.append((name, pdis, optima))
    for arm, label, color in zip(ARMS, LABELS, COLORS):
        gap, cumulative, coverage, proofs = [], [], [], []
        metrics = []
        for seed in seeds:
            for name in names:
                record = records[arm, seed, name]
                metric = record["metrics"]
                metrics.append(metric)
                base = evidence / "raw" / arm / str(seed) / name
                trace = cbc_pdi.build_trace(cbc_pdi.run_events(
                    Path(str(base) + ".log"), Path(str(base) + ".progress.csv"), "csv"),
                    manifest["references"][name]["sense"] == "max")
                curve = cumulative_curve(trace, horizon, grid)
                assert abs(curve[-1] - metric["pdi"]) < 1e-8, (arm, seed, name)
                gap.append(cbc_pdi.gap_curve(trace, horizon, grid))
                cumulative.append(curve)
                first = metric["t_first"]
                coverage.append(grid >= (float("inf") if first is None else first))
                proofs.append(grid >= (metric["elapsed_s"]
                                       if metric["optimal_within_horizon"] else float("inf")))
        reported = summary["cohorts"]["all seeds"][arm]
        assert abs(statistics.mean(m["pdi"] for m in metrics) - reported["mean_pdi"]) < 1e-12
        assert sum(m["optimal_within_horizon"] for m in metrics) == reported["optimal"]
        for ax, data in zip(axes.flat, (gap, cumulative, coverage, proofs)):
            ax.plot(grid, np.mean(data, axis=0), color=color, label=label, linewidth=1.8)
            ax.set_xlabel("Elapsed solve time (seconds)")
            ax.set_xscale("symlog", linthresh=1)
            ax.grid(alpha=.15)
    for ax, title in zip(axes.flat, (
        "Whole-set mean normalized gap", "Accumulated PDI / 1,800-second horizon",
        "Fraction with an incumbent by time", "Fraction proven optimal by time",
    )):
        ax.set_title(title)
    axes[0, 0].legend(fontsize=8)
    fig.savefig(out / "confirmation-trajectories.png", dpi=180)
    plt.close(fig)
    ordered = sorted(model_rows, key=lambda row: row[1][2] - row[1][0])
    fig, ax = plt.subplots(figsize=(10.5, 8.5), constrained_layout=True)
    values = [row[1][2] - row[1][0] for row in ordered]
    ax.barh([row[0] for row in ordered], values,
            color=["#087e8b" if v <= 0 else "#b55d23" for v in values])
    ax.invert_yaxis()
    ax.axvline(0, color="#333333", linewidth=.7)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_xlabel("Candidate PDI minus OFF PDI (four-seed model means; lower is better)")
    ax.set_title("All 47 models: gains and regressions retained")
    fig.savefig(out / "confirmation-model-deltas.png", dpi=180)
    plt.close(fig)
    rng = np.random.default_rng(20261028)
    bootstrap = rng.choice(deltas, size=(10000, len(deltas)), replace=True).mean(axis=1)
    low, high = map(float, np.quantile(bootstrap, [.025, .975]))
    (out / "pdi-bootstrap.json").write_text(json.dumps({
        "candidate_minus_off": statistics.mean(deltas), "ci95": [low, high],
        "resampling_unit": "instance; all four seeds kept together",
        "samples": 10000, "seed": 20261028,
        "limitation": "conditional on this selected, tuning-exposed collection",
    }, indent=2) + "\n")
    all_seeds = summary["cohorts"]["all seeds"]
    improvement = 100 * (1 - all_seeds[ARMS[2]]["mean_pdi"] / all_seeds["off"]["mean_pdi"])
    text = [
        "---", 'title: "CBC SppGrasp: evidence for an adaptive default"',
        'subtitle: "564 validated solves on 47 SPP-dominant models"',
        'date: "28 October 2026"', "fontsize: 10pt", "geometry: margin=20mm",
        "colorlinks: true", "---", "",
        "# Executive result", "",
        (f"The tested 500M-work candidate lowers whole-collection mean PDI by "
        f"**{improvement:.2f}% versus OFF**, preserves **every one of OFF's 104 "
        "optimal solves**, and reduces runs with no incumbent from **16 to 4**. "
        "It recovers both proofs lost by unchanged ON on `eilC76-2` "
        "(seeds 6401 and 6402). There are no proof gains or losses versus OFF."), "",
        ("**This is not a regression-free or universal-dominance claim.** "
        "Mean runtime is 839.85 s versus 839.42 s for OFF (+0.43 s); individual "
        "PDI and final-gap regressions remain. The candidate matches, rather "
        "than exceeds, OFF's optimal count. No AUTO mode or default change has "
        "been implemented by this experiment."), "",
        "# Whole-collection results", "",
        "| Metric | OFF | Unchanged ON | 500M + FPump retained |",
        "|:--|--:|--:|--:|",
    ]
    for label, key, digits in (
        ("Validated optimal solves / 188", "optimal", 0),
        ("Mean PDI (lower is better)", "mean_pdi", 6),
        ("Mean elapsed seconds", "mean_elapsed_s", 2),
        ("No incumbent at 1,800 s", "no_incumbent", 0),
        ("Mean final gap %, same 172 pairs", "mean_common_gap_pct", 3),
    ):
        text.append("| " + label + " | " + " | ".join(
            f"{all_seeds[arm][key]:.{digits}f}" for arm in ARMS) + " |")
    text += [
        "", (f"Paired mean PDI difference, candidate minus OFF: "
        f"**{statistics.mean(deltas):.6f}**; descriptive 95% instance-bootstrap "
        f"interval **[{low:.6f}, {high:.6f}]**. All seeds of each instance are "
        "resampled together (10,000 samples). This interval is conditional on "
        "the selected collection, not an estimate for unseen MIPs."), "",
        "# What was tested", "",
        ("The collection contains **47 SPP-dominant instances**: 29 pure binary "
        "set packing/partitioning models and 18 separately labeled supplemental "
        "RMP application models. Seventeen are from MIPLIB 2017; 30 are collected "
        "application instances. At least 90% of original rows must be packing "
        "or partitioning (actual minimum 92.044%). The feature table and inputs "
        "were frozen before the original performance study."), "",
        ("All 47 models were run in all three arms with four matched seeds: "
        "**6401, 6402, 6601, 6602**. Each solve received **1,800 elapsed seconds**; "
        "16 independent serial CBC processes (`-threads 0`) ran concurrently, "
        "with BLAS/OpenMP restricted to one thread. Task order was shuffled "
        "with scheduling seed 6500. All **564 planned runs validated**."), "",
        "| Arm | Explicit settings |", "|:--|:--|",
        "| OFF | `-sppGrasp off` |",
        "| Unchanged ON | `-sppGrasp on` |",
        "| Candidate | `-sppGrasp on -sppGraspWork 500 -sppGraspFpump on` |", "",
        ("`sppGraspWork 500` is 500 million counted work units per call, not "
        "500 seconds or a hard whole-solve work budget. `sppGraspFpump on` "
        "prevents automatic disabling; it does not force FPump to perform "
        "LP passes when an incumbent already exists. Existing applicability, "
        "native completion and all other search defaults remain in effect."), "",
        ("The arms use the **same frozen optimized, Nauty-free executable** "
        "and dependencies. No model-name gate, input-model modification, forced "
        "applicability or per-instance parameter tuning was applied to the "
        "candidate. Existing automatic artificial-slack behavior is retained."), "",
        "# PDI and solution validation", "",
        ("PDI is the average normalized primal-dual gap over the common "
        "1,800-second horizon. Gap is 2 without an incumbent, 1 with an "
        "incumbent but no usable dual bound (or opposite signs), otherwise "
        "`abs(primal-dual)/max(abs(primal),abs(dual))`, with the analyzer's "
        "zero-gap convention for equal zero bounds. Lower is better. "
        "An optimality/infeasibility proof closes the gap at its actual "
        "timestamp; a stopped run holds its last gap to the horizon."), "",
        ("Every history uses the complete progress CSV, including original-model "
        "incumbents and a positive global final timestamp. No missing CSV or "
        "fractional LP relaxation is converted into an integer solution. "
        "An independent validator checks genuine incumbents against bounds, "
        "integrality, every row and objective; reference objectives cross-check "
        "proof claims. Failed or missing runs block complete reporting."), "",
        ("Conventional final relative gap uses `abs(p-d)/max(abs(p),1e-10)` "
        "and is averaged only over the same 172 finite-bound/incumbent pairs "
        "in all arms. It differs from the normalized PDI gap."), "",
        r"\newpage", "",
        "# Finding solutions and proving optimality over time", "",
        ("![All 188 runs per arm; the final cumulative ordinate equals the "
        "reported mean PDI. Time uses a symmetric log scale near zero."
        "](confirmation-trajectories.png){width=100%}"), "",
        "# Original and fresh seeds", "",
        ("Original seeds deliberately revisit the earlier proof losses. Fresh "
        "seeds provide seed-based replication on the same models, not an "
        "independent-instance holdout."), "",
    ]
    for cohort in ("original seeds", "fresh seeds"):
        text += ["## " + cohort.capitalize(), "",
                 "| Arm | Optimal / 94 | Mean PDI | Mean seconds | No incumbent |",
                 "|:--|--:|--:|--:|--:|"]
        for arm, label in zip(ARMS, LABELS):
            m = summary["cohorts"][cohort][arm]
            text.append(f"| {label} | {m['optimal']} | {m['mean_pdi']:.6f} | "
                        f"{m['mean_elapsed_s']:.2f} | {m['no_incumbent']} |")
        text.append("")
    text += [
        r"\newpage", "", "# Individual-model effects", "",
        ("Each bar averages four matched seeds; negative favors the candidate. "
        "Regressions are retained, not omitted."), "",
        "![Candidate versus OFF on every model.](confirmation-model-deltas.png){width=95%}", "",
        r"\newpage", "", "# Interpretation for AUTO", "",
        ("Forrest's concern is valid: AIR03 profiling exposed expensive local "
        "search, and his 44-problem unit-test timing increased from about "
        "85.4 s to 95.3 s when SppGrasp was enabled. This study does not "
        "refute that measurement or establish that a broad default should "
        "always execute full SppGrasp."), "",
        ("The evidence supports an **AUTO policy proposal**, not simply renaming "
        "unchanged ON. The tested starting point is existing structural "
        "applicability plus a 500M per-call work limit and preservation of "
        "FPump availability, while retaining safe pre-LP native completion. "
        "A general AUTO implementation still needs explicit semantics, "
        "user-override preservation, and broader non-SPP/quick-suite validation. "
        "A cheap structural skip and effort control are hypotheses for that "
        "implementation, not separately proven adaptive decisions here."), "",
        ("The 500M candidate was selected from a seven-policy screen on 11 "
        "models. The confirmation uses all 47 models and fresh seeds but "
        "the collection has tuning/development exposure. Do not describe it "
        "as unseen-instance validation, or assert a guarantee of no regressions. "
        "Timing under concurrent load is noisy; the 0.43 s aggregate runtime "
        "difference is reported, not claimed statistically equivalent."), "",
        "# Reporting fixes and reproducibility", "",
        ("A previous confirmation finished with only 562/564 valid runs: an "
        "OFF `ivu06/6602` preprocessing timeout omitted its CSV, while an ON "
        "timeout reported a saved incumbent but exported the fractional LP "
        "vector. Both original failures remain preserved. A reporting-only "
        "fix restores the saved integer vector and finalizes progress on "
        "that early return. The full 564-run round was restarted with the "
        "same repaired binary in all arms; no old/new results were mixed."), "",
        ("Baseline: `coin-or/Cbc@97ca70c7` (master, OFF default). Reporting-only "
        "source: `f7ef1ae9` (full revision in the manifest), including initial-LP "
        "and preprocessing-timeout repairs. It does not import unrelated next "
        "heuristic changes. Focused timeout probes fail on the old build and "
        "pass after the repair; native/progress/objective-offset, solver quick, "
        "callback and bound tests passed. Nauty was excluded from every arm."), "",
        ("The result directory includes the exact manifest, all source revisions, "
        "commands, input/binary/runtime-library hashes, combined source patch, "
        "per-run metrics, proof transitions and gap regressions. Raw evidence "
        "and frozen executables accompany the experiment release."), "",
        "# References", "",
        ("- [Dataset, model characteristics and attribution]"
        "(https://github.com/h-g-s/set-packing-partitioning-instances)"),
        ("- [Forrest's OFF-default commit and discussion]"
        "(https://github.com/coin-or/Cbc/commit/65e778e18abadcd13a84ad8a900969b08cbc2450"
        "#commitcomment-206687914)"),
        ("- Gleixner et al. (2021), *MIPLIB 2017: Data-Driven Compilation of "
        "the 6th Mixed-Integer Programming Library*, Mathematical Programming "
        "Computation. DOI: [10.1007/s12532-020-00194-3]"
        "(https://doi.org/10.1007/s12532-020-00194-3)."), "",
        r"\newpage", "", "# Appendix: all model means and optimal counts", "",
        ("Optimal counts are out of four seeds per model and arm. No proof "
        "gain or loss occurs between the candidate and OFF."), "",
        "| Model | OFF PDI | ON PDI | Candidate PDI | OFF/ON/Candidate optima |",
        "|:--|--:|--:|--:|:--|",
    ]
    for name, pdis, optima in sorted(model_rows):
        text.append(f"| {name} | {pdis[0]:.6f} | {pdis[1]:.6f} | "
                    f"{pdis[2]:.6f} | {' / '.join(map(str, optima))} |")
    text += ["", "# Appendix: terminal-gap regressions", "",
             ("Retained for transparency, even though final gap is secondary "
             "to PDI, optimal solves and solution availability in this study."), ""]
    for reference, changes in summary["candidate_transitions"].items():
        text += ["## Candidate versus " + reference.upper(), ""]
        for row in changes["gap_regressions_over_001_percentage_points"]:
            text.append(f"- {row['run']}: {row['control']:.5f}% to {row['candidate']:.5f}%.")
        text.append("")
    (out / "UPDATED-REPORT.md").write_text("\n".join(text).rstrip() + "\n")
    with (out / "model-means.tsv").open("w") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(["instance", "off_pdi", "on_pdi", "candidate_pdi",
                         "off_optimal", "on_optimal", "candidate_optimal"])
        for name, pdis, optima in sorted(model_rows):
            writer.writerow([name, *pdis, *optima])
    print(f"Verified 564 runs and all trace integrals; report source: {out}")


if __name__ == "__main__":
    main()
