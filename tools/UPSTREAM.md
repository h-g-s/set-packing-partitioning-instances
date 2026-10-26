# Upstream analysis and validation tools

`cbc_pdi.py` and `cbc_validate_sol.cpp` are unchanged copies from
https://github.com/coin-or/Cbc at commit
`97ca70c7dd1396e3aa66ff6ac0c4860b5fb6f12d`:

- `test/cbc_pdi.py`
- `test/cbc_validate_sol.cpp`

They retain CBC's EPL-2.0 licensing. The feature extractor calls the installed
`OsiFeatures::compute` and `CbcSppGrasp::load`; it does not reimplement either
feature extraction or heuristic eligibility.

New orchestration and reporting scripts are EPL-2.0. They add strict evidence
gating, paired summaries, exact cumulative-integral plots and solution checks
around the existing PDI implementation.
