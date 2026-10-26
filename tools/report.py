#!/usr/bin/env python3
"""Publish complete paired results, explicitly accounting for missing/invalid runs."""

# SPDX-License-Identifier: EPL-2.0
import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import cbc_pdi
import matplotlib.pyplot as plt
import numpy as np


def average(values):
    return statistics.mean(values)


def save_table(path, rows):
    with path.open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def cumulative_curve(trace, horizon, grid):
    times = sorted(
        {0.0, horizon}
        | {t for t, _ in trace.primal + trace.dual if 0 <= t <= horizon}
        | (
            {trace.end_time}
            if trace.status in ("optimal", "infeasible")
            and 0 < trace.end_time < horizon
            else set()
        )
    )
    gaps = np.array(cbc_pdi.gap_curve(trace, horizon, times))
    cumulative = np.r_[0.0, np.cumsum(np.diff(times) * gaps[:-1])]
    indexes = np.searchsorted(times, grid, side="right") - 1
    return (
        cumulative[indexes] + gaps[indexes] * (grid - np.array(times)[indexes])
    ) / horizon


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = a.out.resolve()
    manifest = json.loads((out / "manifest.json").read_text())
    expected = manifest["tasks"]
    problems, records = [], []
    for task in expected:
        path = (
            out
            / "raw"
            / task["arm"]
            / str(task["seed"])
            / (task["instance"] + ".result.json")
        )
        label = f"{task['arm']}/{task['seed']}/{task['instance']}"
        if not path.exists():
            problems.append(f"{label}: missing")
            continue
        record = json.loads(path.read_text())
        if not record["valid"]:
            problems.append(f"{label}: {'; '.join(record['errors'])}")
        else:
            records.append(record)
    if problems:
        report = [
            "# INCOMPLETE - no whole-collection outcome claim",
            "",
            f"{len(records)}/{len(expected)} planned runs validated.",
            "",
            "Missing and invalid runs must not be silently excluded from averages.",
            "",
        ]
        report += ["- " + p for p in problems]
        (out / "REPORT.md").write_text("\n".join(report) + "\n")
        print(f"INCOMPLETE: {len(problems)} missing/invalid runs", file=sys.stderr)
        return 1
    arms = {arm: [r for r in records if r["arm"] == arm] for arm in ("off", "on")}
    lookup = {(r["arm"], r["seed"], r["instance"]): r for r in records}
    names = [r["instance"] for r in manifest["inputs"]]
    seeds = manifest["seeds"]
    pairs = [
        (lookup["off", seed, name], lookup["on", seed, name])
        for name in names
        for seed in seeds
    ]
    flat = [
        dict(
            instance=r["instance"],
            seed=r["seed"],
            arm=r["arm"],
            wall_s=r["wall_s"],
            **r["metrics"],
        )
        for r in records
    ]
    save_table(out / "runs.tsv", flat)
    paired = []
    for row in manifest["inputs"]:
        name = row["instance"]
        selected = {
            arm: [lookup[arm, s, name]["metrics"] for s in seeds] for arm in arms
        }
        off_pdi, on_pdi = (average(r["pdi"] for r in selected[arm]) for arm in arms)
        paired.append(
            {
                "instance": name,
                "cohort": row["cohort"],
                "origin": row["origin"],
                "off_pdi": off_pdi,
                "on_pdi": on_pdi,
                "delta_pdi": on_pdi - off_pdi,
                "off_optimal": sum(
                    r["optimal_within_horizon"] for r in selected["off"]
                ),
                "on_optimal": sum(r["optimal_within_horizon"] for r in selected["on"]),
                "off_elapsed": average(r["elapsed_s"] for r in selected["off"]),
                "on_elapsed": average(r["elapsed_s"] for r in selected["on"]),
                "off_no_incumbent": sum(r["no_incumbent"] for r in selected["off"]),
                "on_no_incumbent": sum(r["no_incumbent"] for r in selected["on"]),
            }
        )
    save_table(out / "paired.tsv", paired)
    matched_gaps = [
        (x["metrics"]["conventional_gap_pct"], y["metrics"]["conventional_gap_pct"])
        for x, y in pairs
        if x["metrics"]["conventional_gap_pct"] is not None
        and y["metrics"]["conventional_gap_pct"] is not None
    ]
    summary = {}
    for i, arm in enumerate(arms):
        ms = [r["metrics"] for r in arms[arm]]
        summary[arm] = {
            "runs": len(ms),
            "optimal": sum(r["optimal_within_horizon"] for r in ms),
            "mean_pdi": average(r["pdi"] for r in ms),
            "mean_elapsed_s": average(r["elapsed_s"] for r in ms),
            "mean_capped_elapsed_s": average(r["capped_elapsed_s"] for r in ms),
            "no_incumbent": sum(r["no_incumbent"] for r in ms),
            "unknown_dual": sum(r["unknown_dual"] for r in ms),
            "normalized_terminal_gap": average(r["final_gap"] for r in ms),
            "common_finite_gap_runs": len(matched_gaps),
            "mean_relative_gap_pct": (
                average(pair[i] for pair in matched_gaps) if matched_gaps else None
            ),
        }
    rng = np.random.default_rng(6401)
    deltas = np.array([p["delta_pdi"] for p in paired])
    bootstrap = rng.choice(deltas, size=(10000, len(deltas)), replace=True).mean(axis=1)
    low, high = np.quantile(bootstrap, [0.025, 0.975])
    summary["paired_pdi_delta_ci95_instance_bootstrap"] = [float(low), float(high)]
    summary["instance_count"] = len(names)
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    gains, losses = [], []
    gap_losses = []
    for x, y in pairs:
        label = f"{x['instance']}/{x['seed']}"
        xo, yo = (r["metrics"]["optimal_within_horizon"] for r in (x, y))
        if yo and not xo:
            gains.append(label)
        if xo and not yo:
            losses.append(label)
        gx, gy = (r["metrics"]["conventional_gap_pct"] for r in (x, y))
        if gx is not None and gy is not None and gy > gx + 0.01:
            gap_losses.append(f"{label}: {gx:.6g}% -> {gy:.6g}%")
    baseline = summary["off"]["mean_pdi"]
    enabled = summary["on"]["mean_pdi"]
    pct = "undefined" if baseline == 0 else f"{100 * (enabled / baseline - 1):+.2f}%"
    report = [
        "# CBC SppGrasp: whole-collection paired results",
        "",
        (
            f"**COMPLETE:** all {len(expected)} planned runs validated; "
            f"{len(names)} models x {len(seeds)} seeds per arm; T={manifest['sec']:g}s."
        ),
        "",
        (
            f"Mean PDI: **{baseline:.6f} off -> {enabled:.6f} on ({pct})**. "
            f"Paired mean difference 95% instance-bootstrap interval: [{low:.6f}, {high:.6f}]."
        ),
        "This interval describes this selected instance set, not an unseen population.",
        "",
        "| Metric | Off | On |",
        "|---|---:|---:|",
    ]
    labels = [
        ("Validated optimal solves by horizon", "optimal"),
        ("Mean PDI (lower is better)", "mean_pdi"),
        ("Mean elapsed seconds (actual final clock)", "mean_elapsed_s"),
        ("Mean elapsed seconds capped at T", "mean_capped_elapsed_s"),
        ("No incumbent by horizon", "no_incumbent"),
        ("Unknown dual by horizon", "unknown_dual"),
        (
            f"Mean final relative gap %, same {len(matched_gaps)} pairs",
            "mean_relative_gap_pct",
        ),
        ("Mean normalized terminal gap penalty (all runs)", "normalized_terminal_gap"),
    ]

    def fmt(v):
        return "-" if v is None else (str(v) if isinstance(v, int) else f"{v:.6g}")

    for label, key in labels:
        report.append(
            f"| {label} | {fmt(summary['off'][key])} | {fmt(summary['on'][key])} |"
        )
    report += [
        "",
        (
            "The conventional relative gap uses |p-d|/max(|p|,1e-10). "
            "It is not the bounded, symmetric PDI gap; missing incumbents are separate."
        ),
        "",
        "![Whole-set PDI and incumbent trajectories](whole-set-pdi.png)",
        "",
        "![Paired per-model PDI changes](paired-pdi.png)",
        "",
        "## Proof and terminal-gap transitions",
        "",
        "Proof gains: " + (", ".join(gains) or "none") + ".",
        "Proof losses: " + (", ".join(losses) or "none") + ".",
        "",
        "Terminal relative-gap regressions >0.01 percentage points:",
        "",
    ]
    report += ["- " + p for p in gap_losses] or ["None."]
    report += [
        "",
        "## Individual models (all seeds averaged)",
        "",
        "| Model | Off PDI | On PDI | On - off | Off optimal | On optimal |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(paired, key=lambda r: r["delta_pdi"]):
        report.append(
            "| {instance} | {off_pdi:.6f} | {on_pdi:.6f} | {delta_pdi:+.6f} | "
            "{off_optimal} | {on_optimal} |".format(**row)
        )
    report += [
        "",
        "## Duplicate off controls",
        "",
        "| Model | Initial off PDI | Repeated off PDI | Repeat - initial |",
        "|---|---:|---:|---:|",
    ]
    for name in manifest["controls"]:
        first = lookup["off", seeds[0], name]["metrics"]["pdi"]
        repeat = lookup["control", seeds[0], name]["metrics"]["pdi"]
        report.append(
            f"| {name} | {first:.6f} | {repeat:.6f} | {repeat - first:+.6f} |"
        )
    report += [
        "",
        (
            "Off-before-on order, concurrent load, prior development exposure and "
            "the selected structural population limit generalization. Enabling the "
            "parameter includes existing FPump/native-completion interactions; "
            "this is not an isolated LNS microbenchmark."
        ),
        "",
        (
            "Machine-readable values: [runs.tsv](runs.tsv), [paired.tsv](paired.tsv), "
            "[summary.json](summary.json). Provenance: [manifest.json](manifest.json)."
        ),
    ]
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    horizon = manifest["sec"]
    grid = np.unique(
        np.r_[0, np.geomspace(0.001, horizon, 2400), np.linspace(0, horizon, 2400)]
    )
    curves = defaultdict(list)
    cumulative = defaultdict(list)
    coverage = defaultdict(list)
    for arm, runs in arms.items():
        for r in runs:
            base = out / "raw" / arm / str(r["seed"]) / r["instance"]
            ev = cbc_pdi.run_events(
                str(base) + ".log", str(base) + ".progress.csv", "csv"
            )
            tr = cbc_pdi.build_trace(
                ev, manifest["references"][r["instance"]]["sense"] == "max"
            )
            curves[arm].append(cbc_pdi.gap_curve(tr, horizon, grid))
            cumulative[arm].append(cumulative_curve(tr, horizon, grid))
            first = r["metrics"]["t_first"]
            coverage[arm].append(grid >= (float("inf") if first is None else first))
    fig, axes = plt.subplots(1, 3, figsize=(17, 5), constrained_layout=True)
    colors = {"off": "#d95f02", "on": "#087e8b"}
    for arm in arms:
        label = f"SppGrasp {arm.upper()}"
        for ax, data in zip(axes, (curves, cumulative, coverage)):
            ax.plot(
                grid,
                np.mean(data[arm], axis=0),
                color=colors[arm],
                label=label,
                linewidth=2,
            )
            ax.set_xlabel("Elapsed solve time (seconds)")
            ax.set_xscale("symlog", linthresh=1)
            ax.grid(alpha=0.2)
        axes[1].fill_between(
            grid, np.mean(cumulative[arm], axis=0), color=colors[arm], alpha=0.08
        )
    for ax, title, ylabel in zip(
        axes,
        (
            "Whole-set mean gap",
            "Accumulated PDI contribution",
            "Models with an integer incumbent",
        ),
        (
            "Normalized gap (0 best; 2 no incumbent)",
            "Integral so far / full horizon",
            "Fraction of model-seed runs",
        ),
    ):
        ax.set_title(title)
        ax.set_ylabel(ylabel)
    axes[0].legend()
    fig.suptitle(
        f"CBC SppGrasp | {len(names)} instances | {len(seeds)} seeds | {horizon:g}s horizon",
        fontsize=16,
        fontweight="bold",
    )
    fig.savefig(out / "whole-set-pdi.png", dpi=180)
    plt.close(fig)
    ordered = sorted(paired, key=lambda r: r["delta_pdi"])
    fig, ax = plt.subplots(
        figsize=(10, max(6, len(names) * 0.23)), constrained_layout=True
    )
    values = [r["delta_pdi"] for r in ordered]
    ax.barh(
        [r["instance"] for r in ordered],
        values,
        color=[colors["on"] if v < 0 else colors["off"] for v in values],
    )
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("PDI(on) - PDI(off): negative favors ON")
    ax.set_title("Every instance retained, including regressions")
    ax.grid(axis="x", alpha=0.2)
    fig.savefig(out / "paired-pdi.png", dpi=180)
    plt.close(fig)
    if "air03" in names:
        subprocess_args = [
            sys.executable,
            str(Path(__file__).with_name("cbc_pdi.py")),
            "--data-dir",
            str(Path(__file__).resolve().parents[1]),
            "explain",
            "--sec",
            str(horizon),
            "--events",
            "csv",
            "--logx",
            "--out",
            str(out / "air03-pdi.png"),
        ]
        for arm in arms:
            subprocess_args.append(
                f"{arm}={out / 'raw' / arm / str(seeds[0]) / 'air03.log'}"
            )
        import subprocess

        subprocess.run(subprocess_args, check=True)
    (out / "REPORT.md").write_text("\n".join(report) + "\n")
    print(
        f"COMPLETE: PDI off={baseline:.6f}, on={enabled:.6f}; report={out / 'REPORT.md'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
