# Reproducing the final report

This directory records the complete, freshly rerun 564-solve comparison.
`REPORT.md` is the frozen launcher's concise summary; `UPDATED-REPORT.md` is
the expanded printable report. Neither includes runs from the preceding
562/564-valid round.

Download `sppgrasp-auto-confirmation-2026-10-28-evidence.tar.gz` from the
[release](https://github.com/h-g-s/set-packing-partitioning-instances/releases/tag/sppgrasp-auto-confirmation-2026-10-28).
The archive contains all 564 result JSONs, progress CSVs, logs, exported
solutions and validation outputs, plus the frozen executables, original
launcher snapshots, manifest, summaries and source patches.
Its uncompressed size is approximately 4 GB.

Verify the archive and PDF against `SHA256SUMS`, then extract the archive into
a separate working directory. With this repository cloned, run:

```sh
python3 tools/confirmation_pdf.py \
  --evidence /path/to/extracted/spp-preprocess-confirm-20261028/full-47-1800s \
  --out /path/to/regenerated-report
cd /path/to/regenerated-report
pandoc UPDATED-REPORT.md --pdf-engine=xelatex \
  -V mainfont='DejaVu Sans' -V monofont='DejaVu Sans Mono' \
  -o sppgrasp-auto-confirmation.pdf
```

The generator verifies every trace integral against the frozen per-run PDI,
checks aggregate PDI and optimal counts, and regenerates both figures, model
means, the fixed-seed instance-cluster bootstrap and printable Markdown.
Python, NumPy, matplotlib, Pandoc, XeLaTeX and the DejaVu fonts are required.
PDF bytes can vary with renderer versions and creation timestamps.

`manifest.json` records exact commands, source revisions, build flags,
input/executable/runtime-library hashes and original paths.
`combined-reporting-fixes-master.patch` applies the reporting repairs to
CBC baseline `97ca70c7dd1396e3aa66ff6ac0c4860b5fb6f12d`; the smaller
`preprocessing-timeout-master.patch` records only the second repair.
All arms use the same reporting-fixed executable and exclude Nauty.

The archived launchers preserve the actual experiment, including absolute
paths; they are not a relocatable turnkey harness. For new solves, use the
manifest's commands with local input/output paths and a matching build.
The frozen executables likewise depend on the recorded host runtime
libraries. Do not mix newly executed runs into the frozen report.
