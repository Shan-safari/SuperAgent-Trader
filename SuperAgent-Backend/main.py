from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.agent import router as agent_router
from routes.trading import router as trading_router

app = FastAPI(title="SuperAgent Backend")

allowed_origins = [
    os.getenv("FRONTEND_URL", "http://localhost:5173"),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in allowed_origins if origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router, prefix="/api/agent", tags=["agent"])

@app.get("/health")
def read_health() -> dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "ok"}
