import os
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()


class AgentQuery(BaseModel):
    prompt: str = Field(..., description="User prompt to send to the agent")


def _build_ollama_payload(prompt: str) -> dict[str, Any]:
    model = os.getenv("OLLAMA_MODEL")
    if not model:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OLLAMA_MODEL is not configured.",
        )

    return {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }


@router.post("/query")
def query_agent(payload: AgentQuery) -> dict[str, Any]:
    """Forward the prompt to the configured Ollama model and return its response."""
    api_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")

    try:
        response = requests.post(api_url, json=_build_ollama_payload(payload.prompt), timeout=120)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to communicate with the Ollama service.",
        ) from exc

    data = response.json()
    text_response = data.get("response") or ""

    return {"response": text_response}
