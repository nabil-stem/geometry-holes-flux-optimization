# Research results

Status: complete

## direct_B01_N6

N=6, Bi=0.1, source=direct, width=0.3. Best observed validated design: greedy_81203; Q=0.3601581 at n=400.

| Method | Median fine gain vs paired initial | Median vs strongest named baseline |
|---|---:|---:|
| random | 0.823% | -0.212% |
| greedy | 1.892% | 0.982% |
| anneal | 1.537% | 0.426% |

![Search](figures/search_direct_B01_N6.png)

![Fields](figures/fields_direct_B01_N6.png)

## direct_B1_N6

N=6, Bi=1, source=direct, width=0.3. Best observed validated design: greedy_81201; Q=1.4510800 at n=400.

| Method | Median fine gain vs paired initial | Median vs strongest named baseline |
|---|---:|---:|
| random | 2.827% | -1.913% |
| greedy | 6.035% | 1.132% |
| anneal | 5.314% | 0.238% |

![Search](figures/search_direct_B1_N6.png)

![Fields](figures/fields_direct_B1_N6.png)

## direct_B10_N6

N=6, Bi=10, source=direct, width=0.3. Best observed validated design: greedy_81201; Q=3.3380264 at n=400.

| Method | Median fine gain vs paired initial | Median vs strongest named baseline |
|---|---:|---:|
| random | 13.989% | -3.951% |
| greedy | 20.197% | 2.736% |
| anneal | 18.161% | -0.148% |

![Search](figures/search_direct_B10_N6.png)

![Fields](figures/fields_direct_B10_N6.png)

## neck_B01_N6

N=6, Bi=0.1, source=neck, width=0.1. Best observed validated design: greedy_81203; Q=0.2309183 at n=400.

| Method | Median fine gain vs paired initial | Median vs strongest named baseline |
|---|---:|---:|
| random | 0.407% | 0.522% |
| greedy | 0.686% | 0.846% |
| anneal | 0.458% | 0.625% |

![Search](figures/search_neck_B01_N6.png)

![Fields](figures/fields_neck_B01_N6.png)

## neck_B1_N6

N=6, Bi=1, source=neck, width=0.1. Best observed validated design: greedy_81205; Q=0.5169781 at n=400.

| Method | Median fine gain vs paired initial | Median vs strongest named baseline |
|---|---:|---:|
| random | 0.178% | 0.197% |
| greedy | 0.325% | 0.363% |
| anneal | 0.089% | 0.137% |

![Search](figures/search_neck_B1_N6.png)

![Fields](figures/fields_neck_B1_N6.png)

## neck_B10_N6

N=6, Bi=10, source=neck, width=0.1. Best observed validated design: greedy_81204; Q=1.3360111 at n=400.

| Method | Median fine gain vs paired initial | Median vs strongest named baseline |
|---|---:|---:|
| random | 0.087% | 0.011% |
| greedy | 0.089% | 0.026% |
| anneal | 0.061% | 0.002% |

![Search](figures/search_neck_B10_N6.png)

![Fields](figures/fields_neck_B10_N6.png)

This is an exploratory finite-budget comparison. Gains use paired starts; method ranking uses all seeds. Source width 0.30 was chosen after the earlier pilot. The demo seeds have not been used to tune the present optimizer. Seed ranges and IQRs describe search variability, not confidence intervals for a global optimum. Mesh-stable means the change in the last two paired flux differences is below the configured fraction of the finest difference; it is a screening criterion, not a rigorous error bound. A fixed-square-size N sweep changes air area and membrane length across N. Keep comparisons within a case separate from comparisons between physical cases.

Status: complete. Paid solves by phase: {'search': 11613, 'validation_fvm': 802, 'mechanism_fvm': 18}. Four initial analytical/linearity check solves are separate.