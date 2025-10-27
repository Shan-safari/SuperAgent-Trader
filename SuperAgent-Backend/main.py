"""FastAPI application exposing a simple health endpoint."""
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="SuperAgent Backend")


@app.get("/health")
def read_health() -> dict[str, str]:
    """Return a lightweight service status indicator."""
    return {"status": "ok"}
