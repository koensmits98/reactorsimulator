from uuid import UUID

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import SimulationRun
from app.db.session import get_db
from app.physics.kinetics import KineticsParams, sample_times, simulate
from app.schemas import SimulationRequest, SimulationResult, Summary

router = APIRouter()


def _to_response(run: SimulationRun) -> SimulationResult:
    return SimulationResult(
        id=run.id,
        created_at=run.created_at,
        parameters=run.parameters,
        summary=Summary(
            peak_power=run.peak_power,
            final_power=run.final_power,
            terminated_early=run.results["terminated_early"],
        ),
        times=run.results["times"],
        power=run.results["power"],
        precursors=run.results["precursors"],
    )


@router.post("/simulations", response_model=SimulationResult, status_code=201)
def create_simulation(req: SimulationRequest, db: Session = Depends(get_db)):
    steps = [(s.time_s, s.absolute) for s in req.reactivity]
    t_eval = sample_times(req.end_time, [t for t, _ in steps], req.max_points)
    result = simulate(
        req.initial_power,
        steps,
        req.end_time,
        KineticsParams(generation_time=req.generation_time),
        t_eval,
    )

    run = SimulationRun(
        parameters=req.model_dump(),
        results={
            "times": result.times.tolist(),
            "power": result.power.tolist(),
            "precursors": result.precursors.tolist(),
            "terminated_early": result.terminated_early,
        },
        peak_power=float(np.max(result.power)),
        final_power=float(result.power[-1]),
    )
    db.add(run)
    db.commit()
    db.refresh(run)  # loads created_at, which the database filled in
    return _to_response(run)


@router.get("/simulations/{run_id}", response_model=SimulationResult)
def get_simulation(run_id: UUID, db: Session = Depends(get_db)):
    run = db.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="simulation not found")
    return _to_response(run)
