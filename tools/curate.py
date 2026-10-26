#!/usr/bin/env python3
"""Extract fresh OsiFeatures and select exact binary packing/partitioning models."""

# SPDX-License-Identifier: EPL-2.0
import argparse
import csv
import hashlib
import io
import json
import shutil
import subprocess
from pathlib import Path


def sha256(path):
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--scanner", type=Path, required=True)
    ap.add_argument("--miplib-list", type=Path, required=True)
    ap.add_argument("--miplib-solu", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument(
        "--reuse-features",
        action="store_true",
        help="reuse the completed extraction after adjusting metadata only",
    )
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    raw = root / "metadata" / "feature-extraction"
    raw.mkdir(parents=True, exist_ok=True)
    files = sorted(a.source.glob("*.mps.gz"))
    if not files:
        raise RuntimeError("No input models")
    if not a.reuse_features:
        subprocess.run(
            [
                "parallel",
                "--jobs",
                str(a.jobs),
                "--halt",
                "soon,fail=1",
                "--joblog",
                str(raw / "joblog.tsv"),
                str(a.scanner.resolve()),
                "{}",
                ">",
                str(raw / "{/.}.tsv"),
                ":::",
            ]
            + [str(p.absolute()) for p in files],
            check=True,
        )
    rows = []
    for path in files:
        result = raw / (path.name.removesuffix(".gz") + ".tsv")
        with result.open() as f:
            text = f.read()
        # Readers can emit informational text; require the known feature header.
        lines = text.splitlines()
        header = next(
            i for i, line in enumerate(lines) if line.startswith("cols\trows\t")
        )
        parsed = list(
            csv.DictReader(io.StringIO("\n".join(lines[header:])), delimiter="\t")
        )
        if len(parsed) != 1:
            raise RuntimeError(f"Malformed feature output: {path}")
        rows.append(dict(instance=path.name.removesuffix(".mps.gz"), **parsed[0]))
    with (root / "metadata" / "all-features.tsv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    miplib = {s.removesuffix(".mps.gz") for s in a.miplib_list.read_text().split()}
    official = {}
    for line in a.miplib_solu.read_text().splitlines():
        tokens = line.split()
        if len(tokens) >= 3 and tokens[0] in ("=opt=", "=best=", "=inf="):
            official[tokens[1]] = tokens[0].strip("="), tokens[2]
    with (a.source / "bks.tsv").open() as f:
        local = {r["instance"]: r["bks"] for r in csv.DictReader(f, delimiter="\t")}
    selected = []
    references = []
    for row in rows:
        name = row["instance"]
        pure = (
            row["strict_binary"] == "1"
            and row["strict_other"] == "0"
            and int(row["strict_partition"]) + int(row["strict_packing"]) > 0
        )
        if not pure and row["spp_native_eligible"] != "1":
            continue
        if (int(row["strict_partition"]) + int(row["strict_packing"])) / float(
            row["rows"]
        ) < 0.9:
            raise RuntimeError(
                f"Model does not satisfy the SPP-dominant definition: {name}"
            )
        dest = root / "instances" / (name + ".mps.gz")
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(a.source / dest.name, dest)
        origin = (
            "MIPLIB 2017"
            if name in miplib
            else (
                "MIPLIB historical"
                if name.startswith("air0")
                else "Collected application"
            )
        )
        url = (
            f"https://miplib.zib.de/instance_details_{name}.html"
            if name in miplib
            else ("https://miplib.zib.de/miplib3/" if name.startswith("air0") else "")
        )
        status, value = official.get(name, ("best", local.get(name, "")))
        # A local BKS may improve an older official value, without being a proof.
        if value and local.get(name) and status != "inf":
            try:
                better = (
                    float(local[name]) < float(value)
                    if row["sense"] == "min"
                    else float(local[name]) > float(value)
                )
            except ValueError:
                better = False
            if better:
                status, value = "best", local[name]
        references.append(
            {
                "instance": name,
                "status": {"opt": "optimal", "inf": "infeasible", "best": "best_known"}[
                    status
                ],
                "objective": "" if status == "inf" else value,
                "sense": row["sense"],
                "source": "MIPLIB v37 / local BKS",
            }
        )
        selected.append(
            {
                "instance": name,
                "rows": int(float(row["rows"])),
                "columns": int(float(row["cols"])),
                "nonzeros": int(float(row["nz"])),
                "partitioning": int(row["strict_partition"]),
                "packing": int(row["strict_packing"]),
                "other_rows": int(row["strict_other"]),
                "cohort": "pure" if pure else "supplemental",
                "native_slack_rows": int(row["spp_slack_rows"]),
                "native_eligible": int(row["spp_native_eligible"]),
                "sense": row["sense"],
                "origin": origin,
                "source_url": url,
                "license": "Original MIPLIB terms" if "MIPLIB" in origin else "EPL-2.0",
                "sha256": sha256(dest),
            }
        )
    if not selected:
        raise RuntimeError("Selection empty")
    for filename, table in (("instances.tsv", selected), ("bks.tsv", references)):
        with (root / filename).open("w") as f:
            writer = csv.DictWriter(f, fieldnames=list(table[0]), delimiter="\t")
            writer.writeheader()
            writer.writerows(table)
    (root / "metadata" / "selection.json").write_text(
        json.dumps(
            {
                "screened": len(rows),
                "selected": len(selected),
                "rule": "pure: binary variables, every raw row all +1 with bounds [1,1] or [-inf,1]; supplemental: remaining native SppGrasp-eligible models",
                "feature_extractor": "OsiFeatures::compute plus raw-row checks and CbcSppGrasp::load",
                "miplib_list_sha256": sha256(a.miplib_list),
                "miplib_solu_sha256": sha256(a.miplib_solu),
            },
            indent=2,
        )
        + "\n"
    )
    table = [
        "# Instance characteristics",
        "",
        "Fresh OsiFeatures extraction; exact raw-row checks define membership.",
        "Native eligibility is a structural check, not a performance label.",
        "",
        "| Instance | Cohort | Rows | Columns | Nonzeros | Partitioning | Packing | Other rows | Native slack rows | Origin |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in selected:
        table.append(
            "| {instance} | {cohort} | {rows} | {columns} | {nonzeros} | {partitioning} | {packing} | "
            "{other_rows} | {native_slack_rows} | {origin} |".format(**r)
        )
    (root / "CHARACTERISTICS.md").write_text("\n".join(table) + "\n")
    print(
        f"Selected {len(selected)}/{len(rows)} models; "
        f"{sum(r['native_eligible'] for r in selected)} native eligible"
    )


if __name__ == "__main__":
    main()
