from fastapi import FastAPI

from app.api import presets, simulations

app = FastAPI(title="Reactor Sandbox", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(simulations.router, prefix="/api")
app.include_router(presets.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
