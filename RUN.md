# Running the Hole-Placement Research Experiments

This directory provides two experiment drivers:

1. **Pilot source-sensitivity study** ([`study.py`](study.py), configured by [`config.json`](config.json), summarized in [`PILOT_RESULTS.md`](PILOT_RESULTS.md)): evaluates a shared 28-layout roster across five source configurations to diagnose supply resistance vs. downstream geometry sensitivity.
2. **Equal-budget placement optimization & regime study** ([`research.py`](research.py), configured by [`config_demo.json`](config_demo.json), [`config_research.json`](config_research.json), and [`config_n_sweep.json`](config_n_sweep.json)): compares **random search**, **greedy single-hole relocation**, and **simulated annealing** from shared initial layouts under identical PDE-solve budgets, followed by multi-grid refinement ($n = 100, 200, 400$), mechanism decomposition, and cross-case transfer evaluation.

---

## 1. Environment Setup

From the parent project directory (`Saad Boualam`) or inside `geometry_holes`:

```powershell
# Base requirements (NumPy, SciPy, Matplotlib, Pydantic)
python -m pip install -r requirements.txt

# Optional research extras (Triangle for independent P1 FEM cross-checks, Ruff, Pytest)
python -m pip install -r requirements-research.txt
```

Verify analytical slab flux, source-scaling linearity, and baseline regression before running searches:

```powershell
python research.py --check-only
```

If the sibling reference repository (`Proba Approach/Antigravity RL method`) is stored in a non-default location, pass `--reference-root "PATH/TO/Antigravity RL method"`.

---

## 2. Preset Experiment Configurations

### A. Quick Demo (`config_demo.json`)
Runs 1 physical case (`direct_B1_N6`: direct west-wall source of width $0.30$, $\mathrm{Bi} = 1.0$, $N = 6$ square holes of side $0.08$), 3 seeds (`81201..81203`), and 3 optimizers (`random`, `greedy`, `anneal`) at a budget of 65 charged PDE solves per run, followed by $n = 200$ and $n = 400$ mesh refinement of all initial layouts, named baselines (`spread`, `proximal`, `distal`, `staggered`), and search endpoints.

```powershell
python research.py --config config_demo.json
```

### B. Source Access $\times$ Permeability Regime Study (`config_research.json`)
Runs 6 physical cases crossing supply architecture (`direct` width $0.30$ vs. `neck` width $0.10$) with membrane Biot number ($\mathrm{Bi} \in \{0.1, 1.0, 10.0\}$) at fixed $N = 6$, 5 seeds (`81201..81205`), and 129 charged PDE solves per task:
- `direct_B01_N6`, `direct_B1_N6`, `direct_B10_N6`
- `neck_B01_N6`, `neck_B1_N6`, `neck_B10_N6`

Also evaluates cross-regime transfer (`transfer.csv`), testing every optimized $N=6$ endpoint in all six `(source, Bi)` regimes to measure whether optimal hole placement shifts with $\mathrm{Bi}$ and source geometry.

```powershell
python research.py --config config_research.json
```

### C. Hole-Count Sweep at Fixed Square Side (`config_n_sweep.json`)
Runs $N \in \{2, 4, 6, 8\}$ with fixed square side $s = 0.08$, minimum gap $0.04$, direct source width $0.30$, and $\mathrm{Bi} = 1.0$ across 5 seeds (`81201..81205`) and 129 solves per task.
> **Important resource policy note:** Keeping square side $s = 0.08$ constant as $N$ increases removes $N s^2$ air area and adds $4 N s$ reactive perimeter. Within each $N$, placement gains are pure geometry effects at fixed area and perimeter; across different $N$, total flux $Q$ reflects both placement and added reactive membrane.

```powershell
python research.py --config config_n_sweep.json
```

### D. Conducting-Neck, Constant-Perimeter Subdivision & Independent FEM Study (`config_extensions.json`)
Runs 9 cases with 3 seeds (`81201..81203`), 65 solves per task, multi-grid refinement ($n=100, 200, 400$), and **independent P1 finite-element cross-checks (`fem_max_areas: [0.0005, 0.0002]`)**:
1. **Conducting (Neumann/reflecting) inlet neck** (`cneck_B01_N6`, `cneck_B1_N6`, `cneck_B10_N6`): tests whether making the narrow inlet duct non-absorbing restores downstream hole-placement sensitivity across $\mathrm{Bi} \in \{0.1, 1.0, 10.0\}$.
2. **Constant-Perimeter Subdivision** (`constP_B1_N3_s016`, `constP_B1_N4_s012`, `constP_B1_N8_s006`, compared with $N=6, s=0.08$): holds total reactive perimeter strictly fixed at $P_{\text{Robin}} = 4.46$ ($4 N s = 1.92$) across $N \in \{3, 4, 6, 8\}$ to test whether fewer large islands or more small islands maximize uptake.
3. **Fixed-Square-Size $N$-Sweep** (`fixedS_B1_N2_s008`, `fixedS_B1_N4_s008`, `fixedS_B1_N8_s008`, compared with $N=6, s=0.08$): varies $N \in \{2, 4, 6, 8\}$ at fixed $s=0.08$.

```powershell
python research.py --config config_extensions.json
```

---

## 3. Resuming Interrupted Runs & Rebuilding Reports

Every search step is journaled immediately to `tasks/<case>/<method>_<seed>/history.jsonl` and `solve_ledger.jsonl`, and completed tasks write `tasks/<case>/<method>_<seed>/summary.json`.

If a run is interrupted, resume it in place without repeating completed `(case, method, seed)` tasks:

```powershell
python research.py --resume results/research_<UTC_TIMESTAMP>
```

To rebuild `report.html`, `report.md`, `method_comparison.csv`, and all PNG figures offline from a completed run directory (without running any new PDE solves):

```powershell
python research_report.py results/research_<UTC_TIMESTAMP>
```

---

## 4. Enabling Independent Conforming FEM Cross-Checks

By default, `fem_max_areas` is `[]` so standard finite-volume runs do not require `triangle`. After installing `requirements-research.txt`, add two or more triangle area bounds (e.g., `"fem_max_areas": [0.0004, 0.0001]`) to your JSON config:

```json
{
  "label": "demo_with_fem",
  "seeds": [81201, 81202, 81203],
  "solve_budget": 65,
  "fem_max_areas": [0.0004, 0.0001],
  "cases": [
    {"name": "direct_B1_N6", "source": "direct", "source_width": 0.3, "Bi": 1, "hole_count": 6}
  ]
}
```

When enabled, [`research_validation.py`](research_validation.py) meshes the exact polygonal boundary of each unique final candidate and solves the boundary-value problem with an independent P1 finite-element assembly (`fem_validation.csv` and the FEM section of `report.html`).

---

## 5. Output Files & How to Read the Results

Each run creates `results/research_<UTC_TIMESTAMP>/` containing:

- **`report.html` and `report.md`**: Self-contained human-readable report with per-case method comparison tables, search convergence trajectories (median and IQR over seeds), refined endpoint scatter plots against named baselines, side-by-side concentration fields (`figures/search_<case>.png`, `figures/fields_<case>.png`), and mechanism decomposition tables.
- **`method_comparison.csv`**: Summary table per `(case, method)` reporting seed count, median fine-grid gain (`n=400`) over the paired initial layout, min-to-max gain range across seeds, median gain over the strongest named baseline, count of mesh-stable paired differences, and budget completion.
- **`assessments.json`**: Per-seed multi-grid verification (`n=100, 200, 400`) checking whether the paired flux improvement $\Delta Q = Q_{\text{best}} - Q_{\text{initial}}$ remains positive across all meshes and changes by less than `gap_change_fraction` (10%) between $n=200$ and $n=400$.
- **`validation.csv`**: Full coarse and refined ($n=100, 200, 400$) metrics (`physical_flux_Q`, `source_influx`, `area`, `robin_perimeter`, `residual_inf`, `conservation_error`) for every initial layout, named baseline, and search endpoint.
- **`mechanisms.json`**: Separates geometric obstruction ($\Delta Q_{\text{obstruction}} = Q_{\text{reflecting}} - Q_{\text{no\_holes}} \le 0$) from reactive island activation ($\Delta Q_{\text{activation}} = Q_{\text{reactive}} - Q_{\text{reflecting}} > 0$), and partitions uptake into inner hole walls (`inner_wall_Q`, `per_hole_Q`) vs. outer chamber walls (`outer_wall_Q`).
- **`transfer.csv`**: Cross-evaluation matrix reporting $Q$ when the best layout found for `origin_case` is evaluated in `target_case` (for all cases sharing the same `hole_count`).
- **`best_designs.json` and `fields/*.npz`**: Coordinates and compressed concentration/flux arrays of the finest-grid winning geometry for each case.
- **`protocol.json`, `provenance.json`, `checks.json`, `solve_ledger.jsonl`, `source_experiment/`, `source_reference/`**: Complete archival snapshot and SHA-256 hashes of the code and solver used.
