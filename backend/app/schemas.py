"""Pydantic models: validation of every request and the shape of every response.

Limits are deliberately strict to protect the small server.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.physics.kinetics import dollars_to_absolute, pcm_to_absolute

MAX_END_TIME_S = 600
MAX_POINTS = 2000
MAX_STEPS = 20
# Absolute reactivity limits (delta-k/k): -50000 pcm to +5000 pcm.
MIN_RHO = -0.5
MAX_RHO = 0.05


class ReactivityStep(BaseModel):
    """From time_s onward, the reactivity is `value` (until the next step)."""

    time_s: float = Field(ge=0, le=MAX_END_TIME_S)
    value: float
    unit: Literal["pcm", "dollars"] = "pcm"

    @property
    def absolute(self) -> float:
        if self.unit == "pcm":
            return pcm_to_absolute(self.value)
        return dollars_to_absolute(self.value)


class SimulationRequest(BaseModel):
    initial_power: float = Field(default=1.0, gt=0, le=1e6)
    generation_time: float = Field(default=1e-4, ge=1e-7, le=1e-2, description="Lambda [s]")
    reactivity: list[ReactivityStep] = Field(min_length=1, max_length=MAX_STEPS)
    end_time: float = Field(gt=0, le=MAX_END_TIME_S)
    max_points: int = Field(default=600, ge=300, le=MAX_POINTS)

    @model_validator(mode="after")
    def check_history(self):
        times = [s.time_s for s in self.reactivity]
        if times[0] != 0:
            raise ValueError("the first reactivity step must be at time_s = 0")
        if any(b <= a for a, b in zip(times, times[1:], strict=False)):
            raise ValueError("reactivity steps must have strictly increasing time_s")
        if times[-1] >= self.end_time:
            raise ValueError("all reactivity steps must happen before end_time")
        for step in self.reactivity:
            if not MIN_RHO <= step.absolute <= MAX_RHO:
                raise ValueError(
                    f"reactivity {step.value} {step.unit} is outside the allowed range"
                )
        return self


class Summary(BaseModel):
    peak_power: float
    final_power: float
    terminated_early: bool


class SimulationResult(BaseModel):
    id: UUID
    created_at: datetime
    parameters: SimulationRequest
    summary: Summary
    times: list[float]
    power: list[float]
    precursors: list[list[float]]  # 6 lists, one per delayed group


class PresetOut(BaseModel):
    id: int
    name: str
    description: str
    parameters: dict[str, Any]
