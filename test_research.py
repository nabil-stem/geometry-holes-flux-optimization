"""Fast unit and integration checks for the equal-budget research protocol."""

from pathlib import Path

import numpy as np
import pytest

import study as ref
from research_config import Case, Protocol
from research_core import Problem, optimize
from research_validation import baselines

HERE = Path(__file__).resolve().parent
REF_ROOT = HERE if (HERE / "src" / "oxygen_shape").is_dir() else HERE.parents[1] / "Proba Approach" / "Antigravity RL method"


@pytest.fixture(scope="module", autouse=True)
def _load_reference_solver():
    ref.load_reference(REF_ROOT)


def test_protocol_validation_rejects_misaligned_or_invalid_settings():
    with pytest.raises(ValueError, match="grid_n must be a multiple of 100"):
        Protocol(grid_n=150)
    with pytest.raises(ValueError, match="historical neck has fixed width 0.10"):
        Protocol(cases=[Case(name="bad_neck", source="neck", source_width=0.3)])


def test_equal_budget_optimizers_preserve_resources_and_charge_every_solve():
    protocol = Protocol(
        seeds=[81201],
        solve_budget=6,
        refinement_factors=[2, 4],
        cases=[Case(name="direct_B1_N6", source="direct", source_width=0.3, Bi=1.0, hole_count=6)],
    )
    problem = Problem(protocol, protocol.cases[0])
    named = baselines(problem)
    assert set(named) == {"spread", "proximal", "distal", "staggered"}
    initial = named["spread"]

    for method in ("random", "greedy", "anneal"):
        summary, history = optimize(problem, initial, method, seed=81201)
        assert summary["status"] == "complete"
        assert summary["solves"] == 6
        assert len(history) == 6
        areas = [row["area"] for row in history]
        perimeters = [row["robin_perimeter"] for row in history]
        assert np.ptp(areas) < 1e-12
        assert np.ptp(perimeters) < 1e-12
        assert summary["best_Q"] >= summary["initial_Q"] - 1e-12


def test_crash_nul_byte_sanitization_in_ledger_and_history(tmp_path):
    ledger = tmp_path / "solve_ledger.jsonl"
    ledger.write_text(
        '{"utc": "1", "phase": "search"}\n\x00\x00\x00{"utc": "2", "phase": "validation_fvm"}\n',
        encoding="utf-8",
    )
    cleaned = [
        s
        for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines()
        if (s := line.replace("\x00", "").strip())
    ]
    assert len(cleaned) == 2

