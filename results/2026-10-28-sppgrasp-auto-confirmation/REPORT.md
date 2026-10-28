# Full-collection SppGrasp effort-policy confirmation

**COMPLETE:** all 564 planned runs validated.
Candidate: SppGrasp ON, 500M work per call, FPump retained.

Same frozen Nauty-free binary in all arms; randomized task order; 1800 seconds per solve. Retaining FPump does not guarantee LP/pass work.

**No default was changed.** This is same-collection confirmation, not independent-instance validation.

This is a fresh replacement round with both initial-LP and preprocessing-timeout reporting fixes applied identically in all arms. The earlier 562/564-valid round is retained separately and is not mixed into these averages.

## All seeds

| Arm | Runs | Optimal | Mean PDI | Mean seconds | No incumbent | Mean gap % |
|---|---:|---:|---:|---:|---:|---:|
| off | 188 | 104 | 0.285123 | 839.42 | 16 | 8.83173 |
| on | 188 | 102 | 0.201818 | 849.18 | 4 | 8.52203 |
| work500-keep-pump | 188 | 104 | 0.200023 | 839.85 | 4 | 8.27488 |

Finite final gap uses the same 172 matched pairs across all three arms.

## Original seeds

| Arm | Runs | Optimal | Mean PDI | Mean seconds | No incumbent | Mean gap % |
|---|---:|---:|---:|---:|---:|---:|
| off | 94 | 52 | 0.283897 | 832.57 | 8 | 8.50163 |
| on | 94 | 50 | 0.203019 | 857.56 | 2 | 8.71599 |
| work500-keep-pump | 94 | 52 | 0.200525 | 836.52 | 2 | 8.30165 |

Finite final gap uses the same 86 matched pairs across all three arms.

## Fresh seeds

| Arm | Runs | Optimal | Mean PDI | Mean seconds | No incumbent | Mean gap % |
|---|---:|---:|---:|---:|---:|---:|
| off | 94 | 52 | 0.286349 | 846.26 | 8 | 9.16184 |
| on | 94 | 52 | 0.200617 | 840.80 | 2 | 8.32806 |
| work500-keep-pump | 94 | 52 | 0.199521 | 843.18 | 2 | 8.24810 |

Finite final gap uses the same 86 matched pairs across all three arms.

## Candidate versus OFF

Proof gains: none.
Proof losses: none.

Final-gap regressions above 0.01 percentage points:

- cod105/6401: 33.61257% -> 33.62634%
- cod105/6402: 33.50752% -> 33.53479%
- ds/6401: 70.10091% -> 81.32828%
- ds/6402: 73.82693% -> 82.44223%
- ds/6602: 75.34253% -> 91.98872%
- eilA101-2/6601: 12.88198% -> 13.39127%
- eilA101-2/6602: 13.36729% -> 14.19117%
- eilB101.2/6401: 7.01992% -> 13.56656%
- eilB101.2/6402: 7.93236% -> 11.30707%
- rmp11/6401: 6.11115% -> 10.47024%
- rmp11/6402: 5.27074% -> 9.71279%
- rmp11/6601: 7.75972% -> 8.54651%
- rmp13/6401: 0.02061% -> 0.03159%
- rmp13/6402: 0.04688% -> 0.06537%
- rmp13/6602: 0.03003% -> 0.04462%
- rmp14/6601: 0.29069% -> 0.36632%
- rmp14/6602: 0.27479% -> 0.46336%
- rmp18/6402: 0.50635% -> 0.75110%
- rmp18/6601: 0.59792% -> 0.69245%
- t1717/6401: 29.49143% -> 31.08301%
- t1717/6402: 30.12918% -> 32.07847%
- t1722/6401: 21.67540% -> 23.30679%
- t1722/6601: 23.10517% -> 23.67526%
- t1722/6602: 14.51908% -> 26.98501%

## Candidate versus ON

Proof gains: eilC76-2/6401, eilC76-2/6402.
Proof losses: none.

Final-gap regressions above 0.01 percentage points:

- cod105/6401: 33.57171% -> 33.62634%
- cod105/6601: 33.45654% -> 33.48377%
- ds/6602: 73.41767% -> 91.98872%
- ds-big/6402: 87.75136% -> 94.39318%
- eilB101.2/6401: 5.97076% -> 13.56656%
- eilB101.2/6601: 3.04014% -> 5.53413%
- eilD76.2/6402: 5.25366% -> 5.29881%
- pdistuchoa/6402: 23.92484% -> 23.95382%
- rmp11/6402: 8.92147% -> 9.71279%
- rmp11/6601: 7.73265% -> 8.54651%
- rmp11/6602: 6.85100% -> 8.98772%
- rmp13/6602: 0.03125% -> 0.04462%
- rmp14/6601: 0.33342% -> 0.36632%
- rmp14/6602: 0.25866% -> 0.46336%
- rmp16/6601: 33.72837% -> 35.02142%
- rmp16/6602: 36.97225% -> 37.57182%
- rmp18/6402: 0.52400% -> 0.75110%
- rmp18/6601: 0.40676% -> 0.69245%
- rmp18/6602: 0.61212% -> 0.65704%
- t1717/6402: 31.12962% -> 32.07847%
- t1717/6601: 30.80197% -> 30.94173%
- t1717/6602: 31.92736% -> 32.32027%
- t1722/6401: 21.08908% -> 23.30679%
- t1722/6601: 20.64669% -> 23.67526%
- t1722/6602: 21.60980% -> 26.98501%

Machine-readable evidence: `confirmation-summary.json`, `screen-runs.tsv`, `diagnostics.json`, and `manifest.json`.
