#!/usr/bin/env python3
"""Run frozen CBC off/on phases with GNU parallel; retain and validate every run."""

# SPDX-License-Identifier: EPL-2.0
import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cbc_pdi

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def read_table(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f, delimiter="\t"))


def save_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def measure(log, progress, reference, sec):
    with progress.open() as f:
        events = list(csv.DictReader(f))
    if not events or events[-1]["source"] != "final":
        raise ValueError("Missing final progress event")
    times = [float(e["time"]) for e in events]
    if any(not math.isfinite(t) or t < 0 for t in times) or times != sorted(times):
        raise ValueError("Non-finite, negative or non-monotonic progress clock")
    if times[-1] <= 0:
        raise ValueError("Non-positive final clock")
    for e in events:
        if not all(math.isfinite(float(e[k])) for k in ("primal", "dual")):
            raise ValueError("Non-finite progress bound")
    ev = cbc_pdi.run_events(str(log), str(progress), "csv")
    if ev.get("event_source") != "progressCsv":
        raise ValueError("PDI attempted approximate log fallback")
    tr = cbc_pdi.build_trace(ev, reference["sense"] == "max")
    if tr.status not in ("optimal", "infeasible", "stopped"):
        raise ValueError(f"Unrecognized terminal status: {tr.status}")
    ref = float(reference["objective"]) if reference["objective"] else None
    sign = -1 if reference["sense"] == "max" else 1
    metric = cbc_pdi.integrate(tr, sec, None if ref is None else sign * ref)
    if metric["pdi"] is None or not math.isfinite(metric["pdi"]):
        raise ValueError("Missing or non-finite PDI")
    primal = cbc_pdi.step_at(tr.primal, sec)
    dual = cbc_pdi.step_at(tr.dual, sec)
    proven = tr.status in ("optimal", "infeasible") and tr.end_time <= sec
    metric["final_gap"] = 0.0 if proven else cbc_pdi.gap_value(primal, dual)
    if tr.status == "infeasible" and reference["status"] != "infeasible":
        raise ValueError("Infeasibility contradicts a known feasible reference")
    if (
        tr.status == "optimal"
        and ref is not None
        and (
            tr.final_primal is None
            or tr.final_primal > sign * ref + max(1e-4, abs(ref) * 1e-4)
        )
    ):
        raise ValueError("Claimed optimum is worse than known feasible reference")
    metric.update(
        status=tr.status,
        elapsed_s=tr.end_time,
        capped_elapsed_s=min(sec, tr.end_time),
        optimal_within_horizon=tr.status == "optimal" and proven,
        no_incumbent=primal is None,
        unknown_dual=dual is None,
        conventional_gap_pct=(
            None
            if primal is None or dual is None
            else 100 * abs(primal - dual) / max(1e-10, abs(primal))
        ),
        event_source="progressCsv",
    )
    return metric


def one(a):
    out = a.out.resolve()
    manifest = json.loads((out / "manifest.json").read_text())
    task = manifest["tasks"][a.task]
    folder = out / "raw" / task["arm"] / str(task["seed"])
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / task["instance"]
    # Names containing a dot are valid instance identifiers; never drop suffixes.
    result_path = Path(str(base) + ".result.json")
    if result_path.exists():
        old = json.loads(result_path.read_text())
        if old["valid"]:
            return
        raise RuntimeError(f"Refusing to overwrite failed evidence: {result_path}")
    log, progress, solution = (
        Path(str(base) + suffix) for suffix in (".log", ".progress.csv", ".sol")
    )
    command = task["command"]
    record = {
        "instance": task["instance"],
        "arm": task["arm"],
        "seed": task["seed"],
        "valid": False,
        "errors": [],
        "command": command,
    }
    start = time.monotonic()
    env = dict(
        os.environ,
        OPENBLAS_NUM_THREADS="1",
        OMP_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
        BLIS_NUM_THREADS="1",
    )
    try:
        with log.open("w") as f:
            f.write(
                "# command: "
                + json.dumps(command)
                + "\n# limit: "
                + str(manifest["sec"])
                + "\n"
            )
            f.flush()
            run = subprocess.run(
                command,
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
                timeout=manifest["sec"] * 1.2,
                check=False,
            )
        record["wall_s"] = time.monotonic() - start
        if run.returncode:
            raise RuntimeError(f"CBC exit {run.returncode}")
        reference = manifest["references"][task["instance"]]
        validation = [str(out / "bin" / "cbc_validate_sol")]
        if reference["status"] in ("optimal", "infeasible"):
            validation += ["--expected-status", reference["status"]]
            if reference["objective"]:
                validation += ["--expected-obj", reference["objective"]]
        validation += [
            str(ROOT / "instances" / (task["instance"] + ".mps.gz")),
            str(solution),
        ]
        with Path(str(base) + ".validation.txt").open("w") as f:
            checked = subprocess.run(
                validation,
                stdout=f,
                stderr=subprocess.STDOUT,
                timeout=180,
                env=env,
                check=False,
            )
        if checked.returncode:
            raise RuntimeError(f"Solution validation exit {checked.returncode}")
        record["metrics"] = measure(log, progress, reference, manifest["sec"])
        record["valid"] = True
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError) as e:
        record["wall_s"] = time.monotonic() - start
        record["errors"].append(f"{type(e).__name__}: {e}")
    save_json(result_path, record)
    print(
        f"{task['arm']}/{task['seed']}/{task['instance']}: "
        f"{'VALID' if record['valid'] else record['errors']}",
        flush=True,
    )
    # Preserve other runs even if this one fails; report explicitly gates results.


def initialize(a):
    out = a.out.resolve()
    if (out / "manifest.json").exists():
        raise RuntimeError("Experiment already exists; use resume")
    (out / "bin").mkdir(parents=True)
    rows = read_table(ROOT / "instances.tsv")
    if a.instances:
        requested = set(a.instances.split(","))
        rows = [r for r in rows if r["instance"] in requested]
        if {r["instance"] for r in rows} != requested:
            raise ValueError("Unknown requested instance")
    references = {r["instance"]: r for r in read_table(ROOT / "bks.tsv")}
    for r in rows:
        model = ROOT / "instances" / (r["instance"] + ".mps.gz")
        if digest(model) != r["sha256"]:
            raise ValueError(f"Input checksum mismatch: {model}")
    for source, name in ((a.cbc, "cbc"), (a.validator, "cbc_validate_sol")):
        shutil.copy2(source, out / "bin" / name)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sec": a.sec,
        "jobs": a.jobs,
        "seeds": a.seeds,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu": subprocess.check_output(["lscpu"], text=True),
        "compiler": subprocess.check_output(
            ["c++", "--version"], text=True
        ).splitlines()[0],
        "binaries": {p.name: digest(p) for p in (out / "bin").iterdir()},
        "inputs": rows,
        "references": {r["instance"]: references[r["instance"]] for r in rows},
        "sources": {},
        "tasks": [],
        "phases": [],
        "controls": [],
        "flags": "-O3 -march=native -mtune=native -ffp-contract=off; static COIN libraries",
        "environment": {
            k: "1"
            for k in (
                "OPENBLAS_NUM_THREADS",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "BLIS_NUM_THREADS",
            )
        },
    }
    if a.source_stack:
        for name in ("CoinUtils", "Osi", "Clp", "Cgl", "Cbc"):
            path = a.source_stack / name
            manifest["sources"][name] = subprocess.check_output(
                ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
            ).strip()
            dirty = subprocess.check_output(
                ["git", "-C", str(path), "diff", "HEAD", "--"], text=True
            )
            if dirty:
                raise RuntimeError(f"Tracked source changes in {name}")
    linked = subprocess.check_output(["ldd", str(out / "bin" / "cbc")], text=True)
    manifest["runtime_libraries"] = linked
    manifest["runtime_library_sha256"] = {}
    for line in linked.splitlines():
        tokens = line.split()
        if "=>" in tokens and len(tokens) > 2 and Path(tokens[2]).is_file():
            manifest["runtime_library_sha256"][tokens[2]] = digest(tokens[2])

    def add_phase(arm, seed, names):
        indexes = []
        for name in names:
            base = out / "raw" / arm / str(seed) / name
            command = [
                str(out / "bin" / "cbc"),
                str(ROOT / "instances" / (name + ".mps.gz")),
                "-timeMode",
                "elapsed",
                "-threads",
                "0",
                "-sec",
                str(a.sec),
                "-randomSeed",
                str(seed),
                "-randomCbcSeed",
                str(seed),
                "-sppGrasp",
                "off" if arm == "control" else arm,
                "-progressCsv",
                str(base) + ".progress.csv",
                "-solve",
                "-solu",
                str(base) + ".sol",
                "-quit",
            ]
            indexes.append(len(manifest["tasks"]))
            manifest["tasks"].append(
                {"arm": arm, "seed": seed, "instance": name, "command": command}
            )
        manifest["phases"].append(indexes)

    for seed in a.seeds:
        for arm in ("off", "on"):
            add_phase(arm, seed, [r["instance"] for r in rows])
    if not a.no_controls:
        controls = [
            n
            for n in ("air03", "ds", "rmp03")
            if n in references and any(r["instance"] == n for r in rows)
        ]
        manifest["controls"] = controls
        add_phase("control", a.seeds[0], controls)
    save_json(out / "manifest.json", manifest)
    return manifest


def execute(a):
    out = a.out.resolve()
    manifest = (
        json.loads((out / "manifest.json").read_text())
        if a.action == "resume"
        else initialize(a)
    )
    if a.action == "prepare":
        print(f"Frozen {len(manifest['tasks'])} tasks in {out}")
        return
    for name, checksum in manifest["binaries"].items():
        if digest(out / "bin" / name) != checksum:
            raise RuntimeError("Frozen executable changed")
    for path, checksum in manifest["runtime_library_sha256"].items():
        if digest(path) != checksum:
            raise RuntimeError("Runtime library changed")
    for row in manifest["inputs"]:
        if digest(ROOT / "instances" / (row["instance"] + ".mps.gz")) != row["sha256"]:
            raise RuntimeError("Frozen input changed")
    for i, tasks in enumerate(manifest["phases"]):
        save_json(
            out / "status.json",
            {
                "phase": i,
                "phases": len(manifest["phases"]),
                "state": "running",
                "pid": os.getpid(),
            },
        )
        subprocess.run(
            [
                "parallel",
                "--jobs",
                str(manifest["jobs"]),
                "--halt",
                "soon,fail=1",
                "--joblog",
                str(out / f"joblog-{i}.tsv"),
                sys.executable,
                str(Path(__file__).resolve()),
                "one",
                "--out",
                str(out),
                "--task",
                "{}",
                ":::",
            ]
            + [str(t) for t in tasks],
            check=True,
        )
    report = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "report.py"), "--out", str(out)],
        check=False,
    )
    if report.returncode:
        (out / "FAILED").write_text(
            "Incomplete or invalid study; inspect report and raw results.\n"
        )
        raise RuntimeError("Study contains failures; report is not a completed result")
    (out / "COMPLETE").write_text(datetime.now(timezone.utc).isoformat() + "\n")
    save_json(out / "status.json", {"state": "complete"})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("prepare", "run", "resume", "one"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cbc", type=Path)
    ap.add_argument("--validator", type=Path)
    ap.add_argument("--source-stack", type=Path)
    ap.add_argument("--sec", type=float, default=1800)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--seeds", type=int, nargs="+", default=[6401, 6402])
    ap.add_argument(
        "--instances", help="comma-separated subset, for smoke testing only"
    )
    ap.add_argument("--no-controls", action="store_true")
    ap.add_argument("--task", type=int)
    a = ap.parse_args()
    if a.sec <= 0 or a.jobs <= 0 or any(s <= 0 for s in a.seeds):
        ap.error("Time, jobs and seeds must be positive")
    if a.action == "one":
        one(a)
    else:
        if a.action in ("prepare", "run") and (a.cbc is None or a.validator is None):
            ap.error("prepare/run requires --cbc and --validator")
        execute(a)


if __name__ == "__main__":
    main()
