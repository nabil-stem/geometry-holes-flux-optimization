"""Validated, explicit research protocol; separate cases never share rankings."""

from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    hole_count: int = Field(default=6, ge=1, strict=True)
    hole_width: float | None = Field(default=None, gt=0)
    Bi: float = Field(default=1, gt=0)
    source: Literal["direct", "neck", "conducting_neck"] = "direct"
    source_width: float = Field(default=.3, gt=0, le=.7)


class Protocol(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    label: str = "placement"
    grid_n: int = Field(default=100, ge=100, strict=True)
    hole_width: float = Field(default=.08, gt=0)
    gap: float = Field(default=.04, gt=0)
    minimum_feature_width: float = Field(default=.04, gt=0)
    position_stride: float = Field(default=.02, gt=0)
    local_step: float = Field(default=.08, gt=0)
    global_move_probability: float = Field(default=.3, gt=0, le=1)
    seeds: list[int] = [81201, 81202, 81203]
    methods: list[Literal["random", "greedy", "anneal"]] = ["random", "greedy", "anneal"]
    solve_budget: int = Field(default=65, ge=2, strict=True)
    max_proposals: int = Field(default=20000, ge=1, strict=True)
    temperature_start: float = Field(default=.02, gt=0)
    temperature_end: float = Field(default=.0002, gt=0)
    refinement_factors: list[int] = [2, 4]
    fem_max_areas: list[float] = []
    practical_gain_percent: float = Field(default=1, gt=0)
    gap_change_fraction: float = Field(default=.1, gt=0, lt=1)
    cases: list[Case] = [Case(name="direct_B1_N6")]

    @model_validator(mode="after")
    def validate_protocol(self):
        if self.grid_n % 100:
            raise ValueError("grid_n must be a multiple of 100")
        if not self.cases or len({c.name for c in self.cases}) != len(self.cases):
            raise ValueError("Declare cases with distinct names")
        if not self.methods or len(set(self.methods)) != len(self.methods):
            raise ValueError("Declare distinct methods")
        if not self.seeds or any(type(s) is not int or s < 0 for s in self.seeds):
            raise ValueError("Seeds must be nonnegative integers")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("Duplicate seeds")
        if self.max_proposals < self.solve_budget-1:
            raise ValueError("max_proposals must cover the solve budget")
        if self.temperature_start < self.temperature_end:
            raise ValueError("The annealing temperature must decrease")
        if self.hole_width < self.minimum_feature_width:
            raise ValueError("Hole width is below the feature cutoff")
        if len(self.refinement_factors) < 2 or len(set(self.refinement_factors)) != len(self.refinement_factors):
            raise ValueError("At least two distinct refinement factors are required")
        if any(type(f) is not int or f < 2 for f in self.refinement_factors):
            raise ValueError("Refinement factors must be integers >=2")
        if self.fem_max_areas and (len(self.fem_max_areas) < 2 or any(
                not np.isfinite(a) or a <= 0 for a in self.fem_max_areas)):
            raise ValueError("FEM validation requires two or more positive mesh areas")
        lengths = [self.hole_width, self.gap, self.minimum_feature_width,
                   self.position_stride, self.local_step]
        for case in self.cases:
            hw = case.hole_width or self.hole_width
            if hw < self.minimum_feature_width:
                raise ValueError("Case hole_width is below the feature cutoff")
            if case.source in ("neck", "conducting_neck") and abs(case.source_width-.1) > 1e-12:
                raise ValueError("The historical neck has fixed width 0.10")
            lengths.extend([hw, case.source_width, .5-case.source_width/2])
            if case.hole_count*(hw+ self.gap)**2 >= .72*.70:
                raise ValueError("Hole count exceeds a conservative packing bound")
        if any(abs(v*self.grid_n-round(v*self.grid_n)) > 1e-10 for v in lengths):
            raise ValueError("Lengths and source endpoints must fit the base mesh")
        if abs(self.local_step/self.position_stride-round(self.local_step/self.position_stride)) > 1e-10:
            raise ValueError("local_step must be a multiple of position_stride")
        return self
