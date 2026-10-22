# Geometry with N holes: optimize total absorbed flux

Read the [Master Research Report](RESEARCH_REPORT.md) for the complete synthesis
of all executed studies, [PILOT_RESULTS.md](PILOT_RESULTS.md) for measured source
sensitivity, mesh checks and concentration figures, and [RUN.md](RUN.md) for
commands and outputs of the full equal-budget optimization and regime study
(`research.py`).

This is a separate experiment from the room-and-door maze model. A fixed outer
air chamber contains N separated square islands excluded from the air. Their
boundaries are reactive Robin membranes. Only island positions vary within a
comparison. The existing maze code and Antigravity repository are unchanged.

## Critique before optimization

The idea is useful: identical movable holes give a small, interpretable design
space with controlled air area and membrane length. One can study obstruction,
mutual screening and access to reactive surfaces without changing graph doors.
However, a hole must have a physical meaning. Here it is a solid/tissue island
with an absorbing surface, not an air opening, ventilation inlet or absorbing
volume. A reflecting obstacle is a different experiment; a diagnostic below
distinguishes obstruction from membrane activation.

The linked [Filoche et al. paper (2008), DOI 10.1073/pnas.0706915105](https://pmc.ncbi.nlm.nih.gov/articles/PMC2409382/)
studies passivation on fixed irregular interfaces. Initially reactive sites
are perfect absorbers (zero-concentration Dirichlet); successively selected
active regions become reflecting (Neumann). Its active region carries 80% of
the flux. It motivates measuring screening, but is not a hole-placement
optimization method. Its sink Dirichlet condition must not be confused with
our supply Dirichlet condition. Its contrasting 2D and 3D behavior also limits
extrapolation of a 2D optimization result. We retain finite Robin permeability
and fixed boundary types during each placement comparison.

Your supplied figure already has equal area and perimeter for the six-hole
layouts. From its rounded numbers, selected search vs spread is about 0.36%,
and selected search vs distal about 1.27%. Selected search vs no holes is
about 2.85%, but that comparison also adds membrane and removes air: it cannot
isolate placement. None of those endpoints proves a global optimum.

## Exact question and constraints

For fixed N, maximize

    Q(X) = integral over all reactive walls of Bi * u_wall ds

subject to

    Laplacian(u) = 0 in air,
    u = 1 on the fixed source,
    du/dn + Bi*u = 0 on reactive walls.

Here Bi = W*L/D, u = (C-Cb)/(C0-Cb), n points out of the air, and X contains
the N square positions. In 2D the dimensional transfer per unit depth is
D*(C0-Cb)*Q when the reference length L is fixed. There is no flow field:
this is diffusive uptake, not ventilation flow optimization.

Within a block, hold outer shape, source position/length, D, W, concentration
driving difference, N, hole width/orientation, minimum gaps and mesh fixed.
Separated identical squares fix both removed area N*s^2 and added perimeter
4*N*s. Enforce clearance to the exterior, clearance between islands, protected
source access and connected air. No touching/merging holes or enclosed air pockets.
The reference solver's operational minimum-feature rule is also enforced.

Only Q determines rankings. Area, perimeter, source influx, residual and balance
are diagnostics. At fixed Bi and perimeter, membrane utilization eta gives the
same ranking; a new efficiency objective is unnecessary.

## A good source: sensitivity, not amplitude

Linearity gives C-Cb = (C0-Cb)*u. Multiplying the driving concentration by a
common positive factor multiplies every dimensional Q by that factor. Relative
gains and rankings are unchanged. Raising C0 cannot turn a 0.3% improvement
into a 10% improvement in this model.

A narrow/long neck can make upstream transport dominate the total resistance.
Then changing downstream holes has little effect. In a simple series-resistance
analogy Q ~ driving_difference/(R_source + R_geometry), so a large R_source
suppresses relative sensitivity to R_geometry. This is a diagnostic analogy,
not an exact reduction of a distributed absorbing domain.

Source width and placement really can change the field and rankings. The pilot
therefore declares these separate source blocks **before** evaluating layouts:

* Original chamber plus width-0.10 inlet neck, reproducing the supplied geometry.
* Same rectangular chamber, with direct west-wall sources of widths 0.10, 0.30,
  0.50 and 0.70, centered at y=0.5; no neck.

A prescribed-concentration source is appropriate for this objective. If the
only supply instead prescribes a fixed total injected flux and all loss is
through the counted membranes, conservation fixes Q to that injection for every
geometry. Then total steady uptake cannot distinguish layouts; concentration
or the required supply potential would need to become the objective.

The rectangle is x in [0.18,0.90], y in [0.15,0.85]. Remaining exterior faces
remain Robin. Widening the source replaces some reactive boundary, so membrane
length differs **between source blocks**. Area and perimeter are fixed **within
each block**. Removing the neck also changes the outer domain. Do not interpret
cross-block Q changes as a gain from better hole placement. The direct-width
sweep isolates source-width effects on one fixed air domain; the neck comparison
is a supply-architecture sensitivity experiment. A perfectly fixed source
cannot simultaneously be an optimization variable.

Choose a source justified by the intended physical setup. For an exploratory
benchmark, prefer a prespecified source with resolved, reproducible placement
sensitivity; retain the entire source sweep. Do not pick the width after seeing
which one makes a favored algorithm or geometry look best. A small converged
effect is a valid scientific finding; no minimum percentage is mathematically
required. Practical usefulness needs your own physical threshold.

## Implemented pilot

`config.json` declares N=6, square side=0.08, gap=0.04, Bi=1, n=100, 24 seeded
random layouts, and refinements n=200 and n=400. Four structured layouts match
the supplied spread/proximal/distal/staggered coordinates. Random proposals
use sequential rejection and deduplication; they are not uniform samples of
all admissible configurations. The same roster is used in every source block,
with full admissibility checks in all blocks before evaluating flux.

The highest Q is the best **among evaluated layouts**, not a claimed optimum.
The random roster is a first search baseline, not an RL implementation. For
other N or hole widths only the random roster is generated; request a nonzero
random_layouts count. Large N may be infeasible for the fixed box and clearance.

For each source block we refine the fixed coarse-grid best, worst and spread
reference (or first layout if there is no spread). Refinement subdivides the
same raster geometry: it does not regenerate positions. Read both absolute Q
and the paired best-minus-reference and best-minus-worst differences. These
selected checks do not establish the ordering of every close competitor.

The selected best also gets an otherwise identical solve with reflecting
island walls. Q_reflecting - Q_no_holes describes obstruction; Q_reactive -
Q_reflecting describes activating island walls. This is a mechanism diagnostic,
not a second objective or a fixed-membrane comparison.

## Run

From this project directory:

```powershell
python -m pip install -r geometry_holes/requirements.txt
python geometry_holes/study.py --check-only
python geometry_holes/study.py
```

The default reference lookup uses the sibling `Proba Approach/Antigravity RL method`
repository. For a different location:

```powershell
python geometry_holes/study.py --reference-root "PATH/TO/Antigravity RL method"
```

Use `--config path.json` and optionally `--out new-directory`. Existing output
directories are rejected. Each run executes an archived copy of `oxygen_shape`,
saves the executed driver/config, SHA-256 source hashes, Python/NumPy/SciPy
versions, actual hole coordinates and concentration masks. It does not install
or modify the reference repository. The complete reference package is copied
for reproducibility; only its geometry and deterministic FVM modules are used.

Checks include an independent exact 1D slab flux, a fresh scaled-RHS solution
demonstrating amplitude linearity, and the supplied geometry's no-hole flux
Q=0.501327287399277 at n=100, Bi=1. Every production solve enforces residual,
concentration bounds and source/absorption balance. Conservation alone does not
establish mesh accuracy.

Outputs in `results/<UTC timestamp>/`:

* `metrics.csv`: all coarse-grid layouts and separate no-hole diagnostics.
* `summary.json`: best observed placements, spreads, source scenarios, solver
  counts and paired refinement differences.
* `refinement.csv`: selected fixed geometries at each grid resolution.
* `layouts.json`, `config.json`, `provenance.json`, `checks.json`, `status.json`.
* `source_sensitivity.png` and `selected_fields.png` (shared linear 0--1 scale;
  red source; white excluded air).
* NPZ fields/masks, executed driver and reference package snapshot.

## Next optimization experiment

1. Freeze one physically motivated source and Bi after the sensitivity study.
2. Use several initial layouts. Move one square at a time; reject invalid
   positions and solve the full PDE for every valid proposal. Accept based on
   Q, not local darkness or local concentration gradients alone.
3. Compare random search, greedy relocation and simulated annealing with equal
   numbers of PDE solves and common initial layouts. Record rejected proposals,
   duplicate layouts, runtime and best-Q trajectories. Keep all seeds.
4. Re-evaluate independent final candidates and close competitors on finer
   meshes. Refinement changes in paired differences should be comfortably below
   the claimed improvement and below the prespecified practical threshold.
5. Map the best observed configuration as N changes using a separate resource
   policy. Fixed hole side makes area decrease and membrane increase with N.
   If instead total removed area is fixed, s ~ N^(-1/2) and perimeter grows as
   sqrt(N); if total added perimeter is fixed, s ~ N^(-1) and removed area shrinks
   as 1/N. Equal squares cannot keep both budgets fixed while changing N. State
   which question is being answered; do not hide this change by setting Bi from
   the new perimeter.

Continuous positions, other shapes, 3D and perfusion can follow once this small
deterministic benchmark has stable rankings. The 2D idealized result is a
mechanistic geometry result and needs additional modeling for physiology.
