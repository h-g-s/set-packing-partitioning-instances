#!/usr/bin/env python3
"""Resume a frozen study and publish its final report and raw evidence."""

# SPDX-License-Identifier: EPL-2.0
import argparse
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repository", required=True)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = a.out.resolve()
    relative = out.relative_to(root)
    run = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "run_study.py"),
            "resume",
            "--out",
            str(out),
        ],
        check=False,
    )
    complete = run.returncode == 0 and (out / "COMPLETE").exists()
    if not complete:
        subprocess.run(
            [sys.executable, str(root / "tools" / "report.py"), "--out", str(out)],
            check=False,
        )
    status = "COMPLETE" if complete else "INCOMPLETE / FAILED"
    (out / "STATUS.md").write_text(
        f"# {status}\n\nUpdated {datetime.now(timezone.utc).isoformat()}.\n\n"
        "See [REPORT.md](REPORT.md). Raw evidence is attached to the experiment release.\n"
        f"Runner exit code: {run.returncode}. No failed or missing run is silently excluded.\n"
    )
    if not (out / "REPORT.md").exists():
        (out / "REPORT.md").write_text(
            "# INCOMPLETE\n\nThe runner or reporting pipeline failed before a report "
            "could be generated. Inspect the raw archive and runner log.\n"
        )
    if not complete:
        report = out / "REPORT.md"
        report.write_text(
            "# INCOMPLETE - runner or reporting failure\n\n" + report.read_text()
        )
    archive = out / "raw-evidence.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name in ("raw", "bin", "manifest.json", "runner.log", "status.json"):
            if (out / name).exists():
                tar.add(out / name, arcname=name)
    subprocess.run(["git", "status", "--short"], cwd=root, check=True)
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=root, check=False
    )
    if staged.returncode != 0:
        raise RuntimeError("Unrelated staged changes found; refusing automatic commit")
    names = ["STATUS.md", "REPORT.md"]
    if complete:
        names += [
            "runs.tsv",
            "paired.tsv",
            "summary.json",
            "whole-set-pdi.png",
            "paired-pdi.png",
        ]
        if (out / "air03-pdi.png").exists():
            names.append("air03-pdi.png")
    subprocess.run(
        ["git", "add"] + [str(relative / name) for name in names], cwd=root, check=True
    )
    subprocess.run(
        ["git", "--no-pager", "diff", "--staged", "--stat"], cwd=root, check=True
    )
    subprocess.run(
        ["git", "--no-pager", "diff", "--staged", "--", "*.md", "*.json", "*.tsv"],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            (
                f"Publish {status.lower()} SppGrasp paired benchmark\n\n"
                "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
            ),
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            "git", "-c",
            (
                "core.sshCommand=ssh -o BatchMode=yes -o ConnectTimeout=10 "
                "-o ServerAliveInterval=10 -o ServerAliveCountMax=2"
            ),
            "push", "origin", "main",
        ],
        cwd=root,
        check=True,
        timeout=120,
    )
    subprocess.run(
        [
            "gh",
            "release",
            "create",
            a.tag,
            str(archive),
            "--repo",
            a.repository,
            "--target",
            "main",
            "--title",
            f"SppGrasp 1800s paired benchmark: {status}",
            "--notes-file",
            str(out / "REPORT.md"),
        ],
        cwd=root,
        check=True,
        timeout=180,
    )
    print(f"Published {status}: {a.repository} / {a.tag}", flush=True)


if __name__ == "__main__":
    main()
