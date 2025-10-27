"""Utilities for querying the local Qwen model via Ollama."""
from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests
from dotenv import load_dotenv

# Ensure environment variables from a local .env file are available when the
# module is imported. Calling load_dotenv multiple times is safe.
load_dotenv()


def _build_payload(prompt: str) -> Dict[str, Any]:
    """Construct the request payload for the Ollama generate API."""
    model = os.getenv("OLLAMA_MODEL", "qwen2.5-7b-instruct")
    return {
        "model": model,
        "prompt": prompt,
        # Stream is disabled because the CLI expects the full reply at once.
        "stream": False,
    }


def query_qwen(prompt: str) -> str:
    """Send the provided prompt to the local Ollama API and return the reply.

    Parameters
    ----------
    prompt:
        The natural language input to send to the model.

    Returns
    -------
    str
        The text of the model's response.

    Raises
    ------
    RuntimeError
        If the Ollama service is unreachable or the response cannot be
        parsed.
    """

    if not prompt:
        raise ValueError("Prompt must be a non-empty string")

    api_url = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    payload = _build_payload(prompt)

    try:
        response = requests.post(api_url, json=payload, timeout=60)
    except requests.RequestException as exc:  # pragma: no cover - network failure
        raise RuntimeError("Failed to reach Ollama API") from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Ollama API returned status {response.status_code}: {response.text}"
        )

    try:
        data: Dict[str, Any] = response.json()
    except json.JSONDecodeError as exc:
        raise RuntimeError("Failed to parse Ollama API response as JSON") from exc

    text = data.get("response") or data.get("output")
    if not isinstance(text, str):
        raise RuntimeError("Ollama response missing 'response' field")

    return text.strip()
