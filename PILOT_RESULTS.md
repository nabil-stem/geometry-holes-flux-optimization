# Executed pilot: 22 October 2026

[Protocol and critique](README.md) ·
[Full saved evidence](results/20261022T071431050562Z/summary.json) ·
[Source sensitivity figure](results/20261022T071431050562Z/source_sensitivity.png) ·
[Best/worst concentration fields](results/20261022T071431050562Z/selected_fields_readable.png)

The placement experiment is promising, and the original inlet masks much of
its sensitivity. Increasing source concentration would not solve that issue;
changing supply geometry does. This is evidence within the present linear,
2D, finite-Robin model.

One shared set of 28 six-hole layouts was evaluated in five source scenarios:
four structured layouts and 24 reproducible random layouts. Square side 0.08,
minimum gap 0.04, Bi=1. Every comparison within a source scenario has equal
air area, equal reactive perimeter and exactly the same source. The production
study used 180 PDE solves, including diagnostics and selected refinements.

| Source scenario | Best observed at n=100 | Best vs worst at n=100 | Best vs spread reference at n=100 |
|---|---|---:|---:|
| Original width-0.10 neck | random_020 | 1.29% | 0.26% |
| Direct width-0.10 source | random_020 | 7.14% | 1.50% |
| Direct width-0.30 source | proximal | 16.05% | 5.78% |
| Direct width-0.50 source | proximal | 25.71% | 9.42% |
| Direct width-0.70 source | proximal | 29.97% | 10.04% |

Percentages are 100*(Q_best/Q_comparator - 1). Best-to-worst spread measures
sensitivity over this roster; it is not the gain of an optimization algorithm
over a good baseline. The best-versus-spread column is the more useful baseline
comparison. This modest random pilot does not beat the original screenshot's
selected search Q=0.51563 in the original neck geometry (pilot best=0.515109).
Its purpose is to diagnose supply sensitivity before a larger search.

The original chamber has air area 0.4836 and reactive perimeter 5.02 after
perforation. Direct sources use air area 0.4656 and perimeters 4.66, 4.46, 4.26,
4.06 for source widths 0.10, 0.30, 0.50, 0.70. Budgets differ between these
separate physical scenarios, so their Q values are not interchangeable evidence
of placement improvement. In the direct-width sweep the air domain stays fixed;
source widening replaces part of the outer reactive wall. The original neck
comparison additionally removes an upstream air region.

## Refinement and verification

The coarse-selected best, worst and spread geometries were held fixed and
subdivided to n=200 and n=400. Their selected ordering remained best > spread >
worst in every block. Only those three candidates per block were refined; this
does not certify the fine-grid winner over all other layouts.

| Source scenario | Best vs selected worst at n=400 | Best vs spread at n=400 |
|---|---:|---:|
| Original neck | 1.23% | 0.27% |
| Direct 0.10 | 6.75% | 1.58% |
| Direct 0.30 | 16.68% | 6.13% |
| Direct 0.50 | 25.93% | 9.46% |
| Direct 0.70 | 30.11% | 10.08% |

From n=200 to n=400, the best-minus-worst absolute Q difference changed by
0.16% to 1.47% of that difference, depending on source scenario. This supports
the observed sensitivity trend and selected order but is not a formal error
bound or proof of full convergence. Maximum recorded relative flux imbalance
was 4.02e-13; maximum algebraic residual was 1.07e-14. Good conservation does
not replace mesh refinement.

Independent checks passed: exact slab flux 0.13333333333333333, source-RHS
scaling error below 1.8e-15, and reproduction of the original no-hole baseline
Q=0.501327287399277. Ruff passed. The saved fields were visually inspected;
`selected_fields_readable.png` was rebuilt from those fields without new solves
to improve title layout. The executed driver and reference solver are archived.

The selected reflecting-hole diagnostic reduces Q relative to the no-hole
domain in all five scenarios. Activating the same island walls adds uptake
and more than compensates that loss. Added reactive wall and obstruction are
therefore distinct mechanisms; looking only at a concentration color map would
miss that distinction.

## What to do next

Use a prespecified direct width-0.30 source as one useful exploratory benchmark:
this pilot resolves a roughly 6% improvement over the spread reference, without
requiring the full west boundary to be a source. This choice is informed by this
pilot and must be evaluated with fresh search seeds; it is not a physiological
calibration or a universally best source. Retain the original-neck case as a
separate supply-limited benchmark. If the application requires that neck,
accept its smaller attainable placement gains.

Then compare random search, greedy relocation and simulated annealing at equal
PDE-solve budgets, with multiple starts and finer evaluation of close finalists.
The objective stays total Q. Moving squares toward the source is a hypothesis,
not a rule: proximal is best here with wider direct sources, but a different
layout wins with the small sources, and other Bi values can change the balance.

For an N-sweep, specify the resource policy first. With fixed square side, N
also changes air area and total membrane. With equal squares and variable N,
fixed total removed area and fixed total added perimeter cannot both hold.
Keep placement optimization within each N and resource comparisons across N
as explicitly different questions.
