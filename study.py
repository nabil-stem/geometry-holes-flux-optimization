"""Fixed-N hole placement pilot; reuse and archive the existing reference solver."""

import argparse
import csv
import hashlib
import json
import platform
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import scipy


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_reference(root):
    sys.path.insert(0, str(root / "src"))
    global RasterGeometry, FaceKey, Side, refine_geometry
    global SquareHole, perforate, maze_chamber, hole_boundary, boundary_hole_ids
    global DiffusionModel, solve, assemble, BoundaryKind
    from oxygen_shape.geometry.raster import RasterGeometry, FaceKey, Side, refine_geometry
    from oxygen_shape.geometry.square_holes import (
        SquareHole, perforate, maze_chamber, hole_boundary, boundary_hole_ids,
    )
    from oxygen_shape.geometry.boundary import BoundaryKind
    from oxygen_shape.physics.model import DiffusionModel
    from oxygen_shape.solvers.finite_volume import solve, assemble


def validate_config(config):
    n, count = config["grid_n"], config["hole_count"]
    if type(n) is not int or n < 100 or n % 100:
        raise ValueError("grid_n must be a positive multiple of 100")
    if type(count) is not int or count < 1:
        raise ValueError("hole_count must be a positive integer")
    if type(config["random_layouts"]) is not int or config["random_layouts"] < 0:
        raise ValueError("random_layouts must be a nonnegative integer")
    if type(config["seed"]) is not int or config["seed"] < 0:
        raise ValueError("seed must be a nonnegative integer")
    for key in ("hole_width", "gap", "Bi"):
        if not np.isfinite(config[key]) or config[key] <= 0:
            raise ValueError(f"{key} must be finite and positive")
    widths = config["source_widths"]
    if not widths or len(set(widths)) != len(widths):
        raise ValueError("Declare distinct source widths")
    for width in widths:
        if not np.isfinite(width) or not 0 < width <= 0.7:
            raise ValueError("Source width must be in (0, 0.7]")
    for value in [config["hole_width"], config["gap"], *widths]:
        if abs(value * n - round(value * n)) > 1e-10:
            raise ValueError("All lengths must fit the base grid exactly")
    for width in widths:
        if abs((0.5 - width / 2) * n - round((0.5 - width / 2) * n)) > 1e-10:
            raise ValueError("Centered source endpoints must fit the grid exactly")
    factors = config["refinement_factors"]
    if len(factors) < 2 or len(set(factors)) != len(factors):
        raise ValueError("Declare at least two distinct refinement factors")
    if any(type(f) is not int or f < 2 for f in factors):
        raise ValueError("Refinement factors must be integers >=2")


def chamber(n, width):
    """Same rectangle for every width; remaining exterior wall stays Robin."""
    mask = np.zeros((n, n), dtype=bool)
    mask[round(0.15*n):round(0.85*n), round(0.18*n):round(0.90*n)] = True
    source = tuple(FaceKey(r, round(0.18*n), Side.WEST) for r in range(
        round((0.5-width/2)*n), round((0.5+width/2)*n)))
    return RasterGeometry(mask, 1/n, source)


def conducting_neck_chamber(n):
    """Same domain as maze_chamber(n), with reflecting (Neumann) inlet neck walls."""
    base = maze_chamber(n)
    r_south, r_north = round(0.45*n), round(0.55*n) - 1
    neumann = tuple(
        FaceKey(r, c, side)
        for r, side in ((r_south, Side.SOUTH), (r_north, Side.NORTH))
        for c in range(round(0.18*n))
    )
    return RasterGeometry(base.inside, base.h, base.source_faces, neumann)


def hole_options(config):
    return dict(gap=config["gap"], protected_length=0.18,
                minimum_feature_width=min(0.04, config["hole_width"], config["gap"]))


def layouts(config):
    """One seeded, outcome-blind roster shared across every source scenario."""
    n, count = config["grid_n"], config["hole_count"]
    width = round(config["hole_width"] * n)
    result = {}
    if count == 6 and abs(config["hole_width"]-0.08) < 1e-12:
        points = {
            "spread": [(x,y) for y in (0.32,0.60) for x in (0.28,0.50,0.72)],
            "proximal": [(x,y) for y in (0.36,0.52) for x in (0.24,0.36,0.48)],
            "distal": [(x,y) for y in (0.36,0.52) for x in (0.52,0.64,0.76)],
            "staggered": [(x,y) for y in (0.26,0.46,0.66) for x in (0.36,0.64)],
        }
        for name, coordinates in points.items():
            holes = tuple(SquareHole(round(y*n), round(x*n), width) for x,y in coordinates)
            perforate(maze_chamber(n), holes, **hole_options(config))
            result[name] = holes
    declared_count = len(result)
    rng = np.random.default_rng(config["seed"])
    # A shared roster must be admissible in every source scenario, including
    # the direct chamber whose left boundary has no neck protrusion.
    outers = [maze_chamber(n), *[chamber(n,w) for w in config["source_widths"]]]
    seen = {tuple(sorted(holes)) for holes in result.values()}
    attempts = 0
    # Sequential rejection is a reproducible proposal law, not uniform sampling.
    while len(result) < declared_count + config["random_layouts"]:
        attempts += 1
        if attempts > 100000:
            raise ValueError("Cannot place the requested holes; reduce N/width/gap")
        holes = []
        for _ in range(10000):
            h = SquareHole(int(rng.integers(round(.15*n), round(.85*n))),
                           int(rng.integers(round(.18*n), round(.90*n))), width)
            try:
                for outer in outers:
                    perforate(outer, tuple(holes+[h]), **hole_options(config))
            except ValueError:
                continue
            holes.append(h)
            if len(holes) == count:
                break
        if len(holes) != count:
            continue
        key = tuple(sorted(holes))
        if key not in seen:
            seen.add(key)
            result[f"random_{len(seen):03d}"] = tuple(holes)
    if not result:
        raise ValueError("No layouts requested")
    return result


def checks(config):
    """Independent analytical slab, source linearity, and supplied-figure regression."""
    from scipy.sparse.linalg import spsolve
    n = 20
    mask = np.ones((4, n), dtype=bool)
    source = tuple(FaceKey(r, 0, Side.WEST) for r in range(4))
    reflecting = tuple(FaceKey(r,c,s) for r,s in ((0,Side.SOUTH),(3,Side.NORTH))
                       for c in range(n))
    g = RasterGeometry(mask, 1/n, source, reflecting)
    bi = 2.0
    res = solve(g, DiffusionModel(Bi=bi))
    exact = 4/n * bi/(1+bi)
    np.testing.assert_allclose(res.metrics.physical_flux_Q, exact, rtol=1e-12)
    system = assemble(g, DiffusionModel(Bi=bi))
    u = spsolve(system.matrix, system.rhs)
    scaled = spsolve(system.matrix, 7*system.rhs)
    np.testing.assert_allclose(scaled, 7*u, rtol=1e-12)
    ref = solve(maze_chamber(100), DiffusionModel(Bi=1))
    np.testing.assert_allclose(ref.metrics.physical_flux_Q, 0.501327287399277, rtol=1e-11)
    return dict(analytical_slab_Q=res.metrics.physical_flux_Q, exact_Q=exact,
                amplitude_scaling_max_error=float(np.max(np.abs(scaled-7*u))),
                original_baseline_Q=ref.metrics.physical_flux_Q)


def run(config, out):
    n, bi = config["grid_n"], config["Bi"]
    model = DiffusionModel(Bi=bi)
    roster = layouts(config)
    write_json(out/"layouts.json", {k:[asdict(h) for h in v] for k,v in roster.items()})
    scenarios = {"original_neck_w0.10": maze_chamber(n)}
    scenarios.update({f"direct_w{w:.2f}": chamber(n,w) for w in config["source_widths"]})
    rows, fine, summaries, fields = [], [], [], {}
    evaluated = 0
    for scenario, outer in scenarios.items():
        block = []
        def evaluate(name, geometry, factor=1, reflecting=False):
            nonlocal evaluated
            if factor > 1:
                geometry = refine_geometry(geometry, factor)
            if reflecting:
                geometry = hole_boundary(geometry, "neumann")
            result = solve(geometry, model)
            evaluated += 1
            m = result.metrics
            row = dict(scenario=scenario, layout=name, n=n*factor, Bi=bi,
                       Q=m.physical_flux_Q, source_influx=m.source_influx,
                       area=m.area, robin_perimeter=m.robin_perimeter,
                       source_length=m.source_length, residual=m.residual_inf,
                       conservation_error=m.conservation_error)
            np.savez_compressed(out/f"{scenario}_{name}_n{n*factor}"
                                f"{'_reflecting' if reflecting else ''}.npz",
                                field=result.concentration, mask=geometry.inside)
            return row, result
        baseline, _ = evaluate("no_holes_diagnostic", outer)
        rows.append(baseline)
        for name, holes in roster.items():
            geometry = perforate(outer, holes, **hole_options(config))
            row, result = evaluate(name, geometry)
            block.append(row)
            rows.append(row)
            fields[(scenario,name)] = result.concentration
        if np.ptp([r["area"] for r in block]) > 1e-12 or np.ptp(
                [r["robin_perimeter"] for r in block]) > 1e-12:
            raise ArithmeticError("Fixed-N area or membrane budget changed")
        ranked = sorted(block, key=lambda r:r["Q"])
        worst, best = ranked[0], ranked[-1]
        reference = next((r for r in block if r["layout"] == "spread"), block[0])
        selected = list(dict.fromkeys([worst["layout"], best["layout"], reference["layout"]]))
        refined_gaps = []
        for factor in sorted([1, *config["refinement_factors"]]):
            values = {}
            for name in selected:
                if factor == 1:
                    row = next(r for r in block if r["layout"] == name)
                else:
                    geometry = perforate(outer, roster[name], **hole_options(config))
                    row, _ = evaluate(name, geometry, factor)
                fine.append(row)
                values[name] = row["Q"]
            refined_gaps.append(dict(n=n*factor,
                best_minus_worst_Q=values[best["layout"]]-values[worst["layout"]],
                best_minus_reference_Q=values[best["layout"]]-values[reference["layout"]]))
        # Mechanism diagnostic: same selected geometry, only island walls reflect.
        geom = perforate(outer, roster[best["layout"]], **hole_options(config))
        reflected, _ = evaluate(best["layout"], geom, reflecting=True)
        summaries.append(dict(scenario=scenario, layouts=len(block),
            best=best["layout"], worst=worst["layout"], reference=reference["layout"],
            best_Q=best["Q"], worst_Q=worst["Q"],
            spread_percent=100*(best["Q"]/worst["Q"]-1),
            gain_over_reference_percent=100*(best["Q"]/reference["Q"]-1),
            no_holes_Q=baseline["Q"], reflecting_selected_Q=reflected["Q"],
            obstruction_delta=reflected["Q"]-baseline["Q"],
            wall_activation_delta=best["Q"]-reflected["Q"], refinement=refined_gaps))
        print(scenario, "best", best["layout"], "spread %",
              f"{summaries[-1]['spread_percent']:.4f}", flush=True)
    write_csv(out/"metrics.csv", rows)
    write_csv(out/"refinement.csv", fine)
    write_json(out/"summary.json", dict(solver_calls=evaluated, scenarios=summaries))
    fig, axes = plt.subplots(1,2,figsize=(12,4.5),layout="constrained")
    for s in summaries:
        data = [r["Q"] for r in rows if r["scenario"] == s["scenario"]
                and r["layout"] != "no_holes_diagnostic"]
        axes[0].plot(np.arange(len(data)), sorted(data), ".-", label=s["scenario"])
    axes[0].set(xlabel="Sorted layout index (different orders per scenario)", ylabel="Total Q")
    axes[0].legend(fontsize=8)
    axes[1].bar(np.arange(len(summaries)), [s["spread_percent"] for s in summaries])
    axes[1].set_xticks(np.arange(len(summaries)), [s["scenario"] for s in summaries], rotation=30)
    axes[1].set(ylabel="100 (best / worst - 1), %", title="Same roster; source sensitivity")
    fig.savefig(out/"source_sensitivity.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(len(summaries),2,figsize=(8,3*len(summaries)),layout="constrained",
                             squeeze=False)
    for axrow, s in zip(axes,summaries):
        for ax, key in zip(axrow,("worst","best")):
            name = s[key]
            im = ax.imshow(fields[(s["scenario"],name)], origin="lower", extent=(0,1,0,1),
                           vmin=0,vmax=1,cmap="viridis")
            for face in scenarios[s["scenario"]].source_faces:
                x=face.col/n
                ax.plot([x,x],[face.row/n,(face.row+1)/n], color="red", linewidth=2)
            ax.set_title(f"{s['scenario']}\n{key}: {name}; Q={s[key+'_Q']:.6f}", fontsize=9)
            ax.set(
                   xlabel="x",ylabel="y")
    fig.colorbar(im,ax=list(axes.flat),label="u, shared linear scale 0 to 1",shrink=.6)
    fig.savefig(out/"selected_fields.png",dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    here = Path(__file__).resolve().parent
    parser.add_argument("--config", type=Path, default=here/"config.json")
    default_ref = here if (here/"src"/"oxygen_shape").is_dir() else here.parents[1]/"Proba Approach"/"Antigravity RL method"
    parser.add_argument("--reference-root", type=Path, default=default_ref)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_config(config)
    reference = args.reference_root.resolve()
    if not (reference/"src"/"oxygen_shape").is_dir():
        parser.error("Pass --reference-root pointing to the Antigravity RL method repository")
    out = args.out or here/"results"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True, exist_ok=False)
    write_json(out/"status.json", dict(status="running", check_only=args.check_only))
    # Execute the frozen copy, leaving the existing project and its runs untouched.
    snapshot = out/"source_reference"
    shutil.copytree(reference/"src"/"oxygen_shape", snapshot/"src"/"oxygen_shape",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy2(__file__,out/"study_executed.py")
    write_json(out/"config.json",config)
    hashes = {str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in out.rglob("*.py")}
    write_json(out/"provenance.json", dict(python=platform.python_version(),
        numpy=np.__version__, scipy=scipy.__version__, source_sha256=hashes))
    load_reference(snapshot)
    write_json(out/"checks.json", checks(config))
    if not args.check_only:
        try:
            run(config,out)
        except Exception as error:
            write_json(out/"status.json", dict(status="failed", error=str(error)))
            raise
    write_json(out/"status.json", dict(status="complete", check_only=args.check_only))
    print(out.resolve())


if __name__ == "__main__":
    main()
