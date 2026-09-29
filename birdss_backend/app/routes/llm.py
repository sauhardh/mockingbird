import os
import logging
import httpx
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any
from . import router

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


class LLMChatRequest(BaseModel):
    model: str = "llama3.2:1b"
    messages: list[dict[str, Any]]
    temperature: float = 0.1
    max_tokens: int = 4096
    response_format: dict[str, Any] | None = None


@router.post("/llm/chat")
async def llm_chat(req: LLMChatRequest):
    payload = {
        "model": req.model,
        "messages": req.messages,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
    }
    if req.response_format:
        payload["response_format"] = req.response_format

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{OLLAMA_HOST}/v1/chat/completions", json=payload)
            if resp.status_code != 200:
                logger.error("Ollama error %s: %s", resp.status_code, resp.text)
                raise HTTPException(status_code=resp.status_code, detail=f"Ollama error: {resp.text}")
            return resp.json()
    except httpx.ConnectError:
        logger.error("Cannot connect to Ollama at %s", OLLAMA_HOST)
        raise HTTPException(
            status_code=503,
            detail=f"Cannot reach Ollama at {OLLAMA_HOST}. Ensure `ollama serve` is running."
        )
    except Exception as e:
        logger.error("Error communicating with Ollama: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
