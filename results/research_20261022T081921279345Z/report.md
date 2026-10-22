# Research results

Status: complete

## direct_B1_N6

N=6, Bi=1, source=direct, width=0.3. Best observed validated design: anneal_81203; Q=1.4453678 at n=400.

| Method | Median fine gain vs paired initial | Median vs strongest named baseline |
|---|---:|---:|
| random | 2.827% | -1.939% |
| greedy | 4.898% | 0.060% |
| anneal | 5.332% | 0.693% |

![Search](figures/search_direct_B1_N6.png)

![Fields](figures/fields_direct_B1_N6.png)

This is an exploratory finite-budget comparison. Gains use paired starts; method ranking uses all seeds. Source width 0.30 was chosen after the earlier pilot. The demo seeds have not been used to tune the present optimizer. Seed ranges and IQRs describe search variability, not confidence intervals for a global optimum. Mesh-stable means the change in the last two paired flux differences is below the configured fraction of the finest difference; it is a screening criterion, not a rigorous error bound. A fixed-square-size N sweep changes air area and membrane length across N. Keep comparisons within a case separate from comparisons between physical cases.

Status: complete. Paid solves by phase: {'search': 585, 'validation_fvm': 48, 'mechanism_fvm': 3}. Four initial analytical/linearity check solves are separate.