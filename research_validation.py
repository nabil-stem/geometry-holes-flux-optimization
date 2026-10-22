"""Fixed-geometry mesh and independent FEM checks of every final candidate."""

from dataclasses import asdict

import numpy as np

import study as ref
from research_core import decode, encode


def baselines(problem):
    if problem.case.hole_count == 6 and abs(problem.config.hole_width-.08) < 1e-12:
        points = {
            "spread": [(x,y) for y in (.32,.60) for x in (.28,.50,.72)],
            "proximal": [(x,y) for y in (.36,.52) for x in (.24,.36,.48)],
            "distal": [(x,y) for y in (.36,.52) for x in (.52,.64,.76)],
            "staggered": [(x,y) for y in (.26,.46,.66) for x in (.36,.64)],
        }
        result = {name: tuple(ref.SquareHole(round(y*problem.n),round(x*problem.n),problem.width)
                              for x,y in xy) for name,xy in points.items()}
        # These baselines are part of the declared experiment; do not silently
        # drop one that becomes invalid under a changed gap or hole width.
        for holes in result.values():
            problem.geometry(holes)
        return result
    return {"fixed_reference": problem.random_layout(np.random.default_rng(9400+problem.case.hole_count))}


class Validator:
    def __init__(self, config, root, ledger=None):
        self.config, self.root = config, root
        self.ledger = ledger or (lambda **kwargs: None)
        self.cache, self.rows, self.fem_rows = {}, [], []
        self.solves = 0

    def evaluate(self, problem, holes, factor):
        holes = tuple(sorted(holes))
        key = (problem.case.name, holes, factor)
        if key in self.cache:
            return self.cache[key]
        geometry = problem.geometry(holes)
        if factor > 1:
            geometry = ref.refine_geometry(geometry, factor)
        result = ref.solve(geometry, problem.model)
        self.solves += 1
        self.ledger(phase="validation_fvm", case=problem.case.name, factor=factor,
                    Q=result.metrics.physical_flux_Q)
        metrics = asdict(result.metrics)
        self.cache[key] = metrics
        if factor == 1:
            # Fields use geometry hashes, enabling exact reuse across reports.
            import hashlib
            digest = hashlib.sha256(geometry.inside.tobytes()).hexdigest()[:16]
            path = self.root/"fields"/f"{problem.case.name}_{digest}.npz"
            path.parent.mkdir(exist_ok=True)
            np.savez_compressed(path, field=result.concentration, mask=geometry.inside,
                                outward_flux=result.outward_face_flux,
                                source_faces=np.array([[f.row,f.col] for f in geometry.source_faces]),
                                h=geometry.h)
            metrics["field_file"] = str(path.relative_to(self.root)).replace("\\","/")
        return metrics

    def validate_case(self, problem, summaries, initial_by_seed):
        candidates = baselines(problem)
        candidates.update({f"initial_{seed}":holes for seed,holes in initial_by_seed.items()})
        candidates.update({f"{s['method']}_{s['seed']}":decode(s["best_holes"]) for s in summaries})
        factors = sorted([1,*self.config.refinement_factors])
        for name, holes in candidates.items():
            for factor in factors:
                m = self.evaluate(problem, holes, factor)
                self.rows.append(dict(case=problem.case.name, candidate=name, factor=factor,
                                      n=problem.n*factor, **m))
        if self.config.fem_max_areas:
            from oxygen_shape.solvers.fem_reference import solve_raster_fem
            unique = {}
            for name,holes in candidates.items():
                unique.setdefault(tuple(sorted(holes)), []).append(name)
            for holes,names in unique.items():
                geometry = problem.geometry(holes)
                for max_area in sorted(self.config.fem_max_areas, reverse=True):
                    result = solve_raster_fem(geometry,problem.case.Bi,max_area)
                    self.ledger(phase="validation_fem",case=problem.case.name,
                                max_area=max_area,Q=result.Q)
                    self.fem_rows.append(dict(case=problem.case.name, candidates=";".join(names),
                        max_area=max_area, Q=result.Q, conservation_error=result.conservation_error,
                        residual=result.residual, area=result.area, robin_perimeter=result.robin_perimeter,
                        vertices=len(result.vertices)))
        assessments = []
        for s in summaries:
            best, initial = decode(s["best_holes"]), initial_by_seed[s["seed"]]
            q = [self.evaluate(problem,best,f)["physical_flux_Q"] for f in factors]
            q0 = [self.evaluate(problem,initial,f)["physical_flux_Q"] for f in factors]
            gaps = np.asarray(q)-q0
            change = abs(gaps[-1]-gaps[-2])
            ratio = change/max(abs(gaps[-1]),1e-14)
            gain = 100*(q[-1]/q0[-1]-1)
            assessments.append(dict(case=problem.case.name, method=s["method"], seed=s["seed"],
                fine_n=problem.n*factors[-1], fine_Q=q[-1], fine_initial_Q=q0[-1],
                fine_gain_percent=gain, paired_gap_change=change,
                paired_gap_change_fraction=ratio,
                positive_gain_all_meshes=bool(np.all(gaps > 1e-12)),
                mesh_gap_stable=bool(ratio <= self.config.gap_change_fraction),
                exceeds_practical_threshold=bool(gain >= self.config.practical_gain_percent),
                field_file=self.evaluate(problem,best,1)["field_file"], holes=encode(best)))
        return assessments

    def mechanism(self, problem, best):
        geometry = problem.geometry(best)
        reactive = self.evaluate(problem,best,1)
        reflecting = ref.solve(ref.hole_boundary(geometry,"neumann"),problem.model)
        no_holes = ref.solve(problem.outer,problem.model)
        from oxygen_shape.geometry.square_holes import boundary_hole_ids
        actual = ref.solve(geometry,problem.model)
        for r in (reflecting, no_holes, actual):
            self.ledger(phase="mechanism_fvm",case=problem.case.name,Q=r.metrics.physical_flux_Q)
        ids = boundary_hole_ids(geometry)
        inner = float(actual.outward_face_flux[ids > 0].sum())
        individual = [float(actual.outward_face_flux[ids == i].sum()) for i in range(1,int(ids.max())+1)]
        qn, q0 = reflecting.metrics.physical_flux_Q, no_holes.metrics.physical_flux_Q
        qr = reactive["physical_flux_Q"]
        if qn > min(q0,qr)+1e-9:
            raise ArithmeticError("Reflecting-obstacle energy monotonicity violated")
        return dict(case=problem.case.name, Q_reactive=qr, Q_reflecting=qn, Q_no_holes=q0,
                    obstruction_delta=qn-q0, activation_delta=qr-qn,
                    inner_wall_Q=inner, outer_wall_Q=qr-inner, per_hole_Q=individual,
                    extra_fvm_solves=3)
