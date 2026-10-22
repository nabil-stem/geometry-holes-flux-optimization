"""Geometry proposals and charged black-box optimization of global uptake."""

import hashlib
import math
import time
from collections import Counter
from dataclasses import asdict

import numpy as np

import study as ref


def encode(holes):
    return [asdict(h) for h in sorted(holes)]


def decode(values):
    return tuple(ref.SquareHole(**h) for h in values)


class Problem:
    def __init__(self, protocol, case):
        self.config, self.case = protocol, case
        self.n = protocol.grid_n
        self.width = round(protocol.hole_width*self.n)
        self.stride = round(protocol.position_stride*self.n)
        self.step = round(protocol.local_step*self.n)//self.stride
        self.outer = (ref.maze_chamber(self.n) if case.source == "neck"
                      else ref.chamber(self.n, case.source_width))
        self.options = dict(gap=protocol.gap, protected_length=.18,
                            minimum_feature_width=protocol.minimum_feature_width)
        self.model = ref.DiffusionModel(Bi=case.Bi)
        # Common position lattice anchored to the fixed physical bounding box.
        gap = round(protocol.gap*self.n)
        self.rows = np.arange(round(.15*self.n)+gap,
                              round(.85*self.n)-gap-self.width+1, self.stride)
        self.cols = np.arange(round(.18*self.n)+gap,
                              round(.90*self.n)-gap-self.width+1, self.stride)
        if not len(self.rows) or not len(self.cols):
            raise ValueError("No feasible positions on the declared lattice")
        self.reference_resources = None

    def geometry(self, holes):
        if len(holes) != self.case.hole_count:
            raise ValueError("Wrong number of holes")
        geometry = ref.perforate(self.outer, tuple(holes), **self.options)
        if any(h.width != self.width for h in holes):
            raise ValueError("Hole dimensions changed")
        return geometry

    def evaluate(self, holes):
        result = ref.solve(self.geometry(holes), self.model)
        resource = (result.metrics.area, result.metrics.robin_perimeter,
                    result.metrics.source_length)
        if self.reference_resources is None:
            self.reference_resources = resource
        if not np.allclose(resource, self.reference_resources, rtol=0, atol=1e-12):
            raise ArithmeticError("Fixed area, perimeter or source changed")
        return result

    def random_position(self, rng):
        return ref.SquareHole(int(rng.choice(self.rows)), int(rng.choice(self.cols)), self.width)

    def random_layout(self, rng, attempt_limit=4000):
        holes = []
        for _ in range(attempt_limit):
            candidate = self.random_position(rng)
            try:
                ref.perforate(self.outer, tuple(holes+[candidate]), **self.options)
            except ValueError:
                continue
            holes.append(candidate)
            if len(holes) == self.case.hole_count:
                return tuple(sorted(holes))
        raise ValueError("Random packing attempt limit reached")

    def relocation(self, current, rng):
        index = int(rng.integers(len(current)))
        if rng.random() < self.config.global_move_probability:
            target = self.random_position(rng)
        else:
            h = current[index]
            dr, dc = rng.integers(-self.step, self.step+1, size=2)*self.stride
            target = ref.SquareHole(max(0,h.row+int(dr)), max(0,h.col+int(dc)), self.width)
        proposed = (*current[:index], target, *current[index+1:])
        self.geometry(proposed)
        return tuple(sorted(proposed))


def optimize(problem, initial, method, seed, journal=None):
    """Every evaluated unique layout costs one solve, including the shared start.

    Rejected/duplicate proposals do not cost solves, but count against a finite
    raw-proposal cap. No field cache is shared between methods. Anneal retains
    a separate best-so-far state; its final current state may have lower Q.
    """
    config = problem.config
    proposal_rng = np.random.default_rng(np.random.SeedSequence([seed, 17]))
    accept_rng = np.random.default_rng(np.random.SeedSequence([seed, 29]))
    started = time.perf_counter()
    initial = tuple(sorted(initial))
    current = best = initial
    result = problem.evaluate(current)
    current_q = best_q = initial_q = result.metrics.physical_flux_Q
    history, rejections = [], Counter()
    seen, raw = {initial}, 0

    def record(candidate, candidate_q, accepted, temperature):
        m = result.metrics
        row = dict(solve=len(history)+1, raw_proposals=raw, candidate_Q=candidate_q,
                   current_Q=current_q, best_Q=best_q, accepted=bool(accepted),
                   temperature=temperature, elapsed_seconds=time.perf_counter()-started,
                   area=m.area, robin_perimeter=m.robin_perimeter,
                   source_length=m.source_length, conservation_error=m.conservation_error,
                   residual=m.residual_inf, candidate_holes=encode(candidate),
                   current_holes=encode(current), best_holes=encode(best))
        history.append(row)
        if journal is not None:
            journal(row)

    record(initial, initial_q, True, config.temperature_start)
    while len(history) < config.solve_budget and raw < config.max_proposals:
        raw += 1
        try:
            candidate = (problem.random_layout(proposal_rng) if method == "random"
                         else problem.relocation(current, proposal_rng))
        except ValueError as error:
            rejections[str(error)] += 1
            continue
        if candidate in seen:
            rejections["Duplicate unordered layout"] += 1
            continue
        result = problem.evaluate(candidate)
        seen.add(candidate)
        candidate_q = result.metrics.physical_flux_Q
        progress = (len(history)-1)/max(config.solve_budget-2, 1)
        temperature = config.temperature_start*(config.temperature_end/config.temperature_start)**progress
        delta = (candidate_q-current_q)/initial_q
        accepted = candidate_q > current_q
        if method == "anneal" and not accepted:
            accepted = accept_rng.random() < math.exp(min(0,delta/temperature))
        if accepted:
            current, current_q = candidate, candidate_q
        if candidate_q > best_q:
            best, best_q = candidate, candidate_q
        record(candidate, candidate_q, accepted, temperature)
    status = "complete" if len(history) == config.solve_budget else "proposal_cap_reached"
    summary = dict(method=method, seed=seed, status=status, solves=len(history),
                   budget=config.solve_budget, raw_proposals=raw,
                   rejected_proposals=dict(rejections), initial_Q=initial_q,
                   best_Q=best_q, final_current_Q=current_q,
                   gain_percent=100*(best_q/initial_q-1),
                   elapsed_seconds=time.perf_counter()-started, best_holes=encode(best),
                   initial_holes=encode(initial), initial_geometry_sha256=hashlib.sha256(
                       problem.geometry(initial).inside.tobytes()).hexdigest())
    return summary, history
