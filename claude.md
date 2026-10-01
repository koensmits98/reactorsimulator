
# Reactor Sandbox

An interactive educational website about how a nuclear reactor works. Each chapter
explains a concept and contains an interactive widget whose physics is computed by
a Python backend through a REST API. First chapter: point reactor kinetics.

## Why this project exists

- A public showcase of full-stack skills: API design and implementation (FastAPI),
  PostgreSQL with SQLAlchemy, Docker, CI/CD and deployment, built on real reactor
  physics.
- The author is a nuclear engineer learning web development. He must understand and
  be able to defend every line. See "Working agreements" below.

## Working agreements for Claude

- Explain design choices briefly when making them, especially anything web, database
  or DevOps related. Physics can be explained more tersely.
- Keep code simple and readable. No premature abstraction, no unnecessary libraries.
- Small, focused commits with clear messages.
- Every physics function gets tests that check known analytical results.
- When the author asks to implement something himself, give guidance and review
  instead of writing the code.

## Tech stack

- Backend: Python 3.12, FastAPI, Pydantic v2, NumPy, SciPy
- Database: PostgreSQL 16, SQLAlchemy 2.x, Alembic for migrations
- Frontend (phase 1): static HTML, CSS and vanilla JavaScript, with a lightweight
  charting library (uPlot or Chart.js). Phase 2: React + TypeScript with Vite.
- Reverse proxy: Caddy (serves the static frontend, proxies /api, automatic HTTPS)
- Tooling: ruff (lint and format), pytest, Docker, Docker Compose
- CI/CD: GitHub Actions, images pushed to GitHub Container Registry (ghcr.io)

## Repository layout

```
backend/
  app/
    main.py          FastAPI app, routers
    api/             route modules (simulations.py, presets.py)
    physics/         kinetics.py and future modules, no web code in here
    db/              models.py, session.py
    schemas.py       Pydantic request and response models
  alembic/
  tests/
  Dockerfile
  pyproject.toml
frontend/
  index.html, kinetics.html, js/, css/
deploy/
  Caddyfile
docker-compose.yml           local development
docker-compose.prod.yml      production on the droplet
.github/workflows/ci.yml
```

Keep physics independent of FastAPI so it can be tested and reused on its own.

## Physics: point kinetics (chapter 1)

Equations, with external source S for the subcritical chapter:

    dP/dt   = (rho - beta) / Lambda * P + sum_i lambda_i * C_i + S
    dC_i/dt = beta_i / Lambda * P - lambda_i * C_i,   i = 1..6

Default delayed neutron data: six-group Keepin data for thermal fission of U-235
(verify values and cite the source in the code and on the website).

- Total beta about 0.0065
- Relative group fractions: 0.033, 0.219, 0.196, 0.395, 0.115, 0.042
- Decay constants lambda_i [1/s]: 0.0124, 0.0305, 0.111, 0.301, 1.14, 3.01
- Default prompt generation time Lambda: 1e-4 s (typical LWR order of magnitude)

Numerics:

- The system is stiff: use scipy.integrate.solve_ivp with method "Radau" or "BDF".
- Start from equilibrium: C_i(0) = beta_i * P(0) / (Lambda * lambda_i).
- Reactivity is a piecewise function of time (rod moves, SCRAM). Integrate segment by
  segment between reactivity changes rather than passing discontinuities to the solver.
- Accept reactivity in pcm or dollars at the API level, convert internally to absolute.

Later physics modules (do not build yet):

1. Temperature feedback: lumped fuel and coolant heat balance with Doppler and
   moderator temperature coefficients.
2. Subcritical with external source (accelerator driven systems).
3. One-group diffusion in a 1D slab or cylinder (flux shape, rod position).
4. Cross section viewer with JEFF 4.0 data stored in PostgreSQL (thinned for display).

No neutron transport solving: out of scope for this project and this server.

## Required physics tests

- rho = 0: power stays constant.
- Small positive step: after transients, power grows with a stable period matching the
  inhour equation.
- Prompt jump: right after a step, P1/P0 is close to beta / (beta - rho) for rho < beta.
- Subcritical with source: steady state P = -S * Lambda / rho.
- SCRAM (large negative step): fast prompt drop, then decay governed by the longest
  lived group (period about 80 s).

## API (v1)

All routes under /api. Pydantic validates every input with strict limits to protect
the small server.

- GET  /api/health                 liveness check
- GET  /api/presets                predefined scenarios (rod withdrawal, prompt
  critical excursion, SCRAM from full power)
- POST /api/simulations            body: initial power, Lambda, reactivity history as a
  list of (time, reactivity) steps, end time.
  Returns a downsampled time series of P and C_i,
  stores the run, returns its id.
- GET  /api/simulations/{id}       retrieve a stored run (shareable link)
- POST /api/kinetics/step          stateless stepping for the live widget: body holds
  the current state (P, C_i), reactivity and dt;
  returns the new state. Lets the frontend run a
  "live" reactor driven by a slider and SCRAM button.

Limits: end time at most 600 s, at most 2000 returned points, step dt at most 5 s,
request bodies small. Return clear 422 errors for invalid input.

## Database

Tables (via SQLAlchemy models and Alembic migrations):

- presets: id, name, description, parameters (JSONB)
- simulation_runs: id (UUID), created_at, parameters (JSONB), results (JSONB,
  downsampled), summary fields (peak power, final power)

Never expose the database port outside the Docker network.

## Deployment target and constraints

DigitalOcean droplet, smallest tier: about 512 MB RAM, 1 vCPU, 10 GB disk.

- Run a single Uvicorn worker.
- Configure PostgreSQL for low memory (for example shared_buffers 32MB,
  max_connections 20).
- A 1 to 2 GB swap file exists on the droplet.
- Never build images on the droplet. CI builds and pushes to ghcr.io; the droplet only
  runs `docker compose pull` and `docker compose up -d`.
- Only ports 22, 80 and 443 open in the firewall. Caddy handles HTTPS.
- Secrets (database password, deploy SSH key) live in GitHub Actions secrets and a
  .env file on the server, never in the repository.

## CI/CD pipeline (GitHub Actions)

1. On every push and pull request: ruff check, pytest (with a PostgreSQL service
   container).
2. On push to main: build backend image, push to ghcr.io, deploy over SSH to the
   droplet.

## Milestones

M1 (first weekend, priority):

- Kinetics solver with the required tests
- POST /api/simulations, GET /api/simulations/{id}, GET /api/presets
- PostgreSQL with Alembic migration, runs stored
- Static frontend page: reactivity slider, SCRAM button, power plot (log scale option)
- Docker Compose running everything locally
- CI running lint and tests
- README with screenshots and an explanation of the architecture

M2: deploy to the droplet with Caddy and the CD step.
M3: live widget via /api/kinetics/step.
M4: temperature feedback chapter.
M5: subcritical / ADS chapter.
M6: React + TypeScript frontend.
M7: 1D diffusion chapter, then the JEFF 4.0 cross section viewer.
