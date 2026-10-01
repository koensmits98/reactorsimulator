# Reactor Sandbox

An interactive educational website about how a nuclear reactor works. Each chapter
explains a concept and has a widget whose physics is computed by a Python backend.
Chapter 1: point reactor kinetics (delayed neutrons, prompt jump, SCRAM).

<!-- TODO: add screenshots of the kinetics page here -->

## Run it locally

```
docker compose up --build
```

Open http://localhost:8080 (API docs at http://localhost:8080/api/docs).

## Architecture

```
browser ──► Caddy ──► static files (frontend/)
              │
              └─ /api/* ──► FastAPI (backend/) ──► PostgreSQL
                              │
                              └─ app/physics/kinetics.py  (pure Python, no web code)
```

- **Caddy** serves the static frontend and proxies `/api` to the backend, so the browser
  sees one origin (no CORS). In production it also handles HTTPS automatically.
- **FastAPI** validates every request with Pydantic (strict limits: end time at most
  600 s, at most 2000 points, at most 20 reactivity steps) and answers invalid input
  with a 422 that names the offending field.
- **Physics** lives in `backend/app/physics/` and knows nothing about the web. It solves
  the six-group point kinetics equations with SciPy's implicit Radau method (the system
  is stiff), integrating segment by segment between reactivity changes.
- **PostgreSQL** stores the presets and every simulation run (JSONB for parameters and
  downsampled results). Runs have a UUID, which makes a result a shareable link:
  `kinetics.html#<run id>`. The schema is managed with Alembic.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | liveness check |
| GET | `/api/presets` | predefined scenarios (each `parameters` is a valid simulation body) |
| POST | `/api/simulations` | run a simulation, store it, return the time series and its id |
| GET | `/api/simulations/{id}` | retrieve a stored run |

Example body (reactivity in `pcm` or `dollars`):

```json
{"initial_power": 1.0,
 "reactivity": [{"time_s": 0, "value": 0}, {"time_s": 10, "value": 100, "unit": "pcm"}],
 "end_time": 120}
```

## Development without Docker

Needs Python 3.12 and a PostgreSQL server.

```
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://reactor:reactor@localhost:5432/reactor
.venv/bin/alembic upgrade head
.venv/bin/pytest          # physics tests need no database; API tests do
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/uvicorn app.main:app --reload
```

## Physics tests

Each checks a known analytical result: constant power at rho = 0; stable period against the
inhour equation; prompt jump `P1/P0 = beta / (beta - rho)`; subcritical steady state
`P = -S * Lambda / rho`; SCRAM decay with the 80 s period of the longest-lived group.

## Status

Milestone 1 (kinetics solver, API, database, frontend, Docker Compose, CI). Deployment
(M2) and the live stepping endpoint (M3) are not built yet.

Delayed neutron data: six-group Keepin data for thermal fission of U-235.
