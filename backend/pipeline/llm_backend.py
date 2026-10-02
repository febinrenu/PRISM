"""
Phase 3 — unified LLM backend abstraction (Module D/E/F).

A single async surface (`generate` / `stream_generate`) that dispatches to the
configured backend so RAG, chat, and reasoning code never hard-code Ollama:

    LLM_BACKEND=ollama            → local Phi-3.5-mini (dev default)
    LLM_BACKEND=ollama_finetuned  → local QLoRA-merged model (Module E)
    LLM_BACKEND=groq              → Groq cloud llama-3.1-8b-instant (production)

The structured causal extractor (`llm_extractor.py`) keeps its own dedicated
Ollama call — it needs `format:"json"` + a warmup and is deliberately pinned to
the local Phi-3.5 for reproducibility of Phase 2 results. This module serves the
conversational / free-form path where a cloud fallback is useful when deployed.
"""
from typing import AsyncIterator, Optional

import httpx

from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_URL,
    LLM_BACKEND,
    LLM_GEN_TIMEOUT_S,
    LLM_NUM_CTX,
    LLM_SEED,
    LLM_TEMPERATURE,
    OLLAMA_FT_MODEL,
    OLLAMA_MODEL,
    OLLAMA_URL,
)

# Connect fast, but tolerate a long wait for the first token (cold model load +
# large-prompt eval). Per-token reads while streaming stay well under this.
_TIMEOUT = httpx.Timeout(LLM_GEN_TIMEOUT_S, connect=10.0)


def _resolve() -> tuple[str, str]:
    """Return (backend, model) for the active configuration."""
    backend = LLM_BACKEND
    if backend == "groq":
        return "groq", GROQ_MODEL
    if backend == "ollama_finetuned":
        return "ollama", OLLAMA_FT_MODEL
    return "ollama", OLLAMA_MODEL


def active_backend() -> dict:
    """Status descriptor for /health, admin dashboard, and chat UI."""
    kind, model = _resolve()
    return {
        "backend": LLM_BACKEND,
        "kind": kind,
        "model": model,
        "cloud": kind == "groq",
        "configured": bool(GROQ_API_KEY) if kind == "groq" else True,
    }


# ── Ollama ────────────────────────────────────────────────────────────────

async def _ollama_generate(
    prompt: str, system: Optional[str], model: str,
    temperature: float, num_predict: int, client: httpx.AsyncClient,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict,
                    "num_ctx": LLM_NUM_CTX, "seed": LLM_SEED},
    }
    if system:
        payload["system"] = system
    r = await client.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json().get("response", "")


async def _ollama_stream(
    prompt: str, system: Optional[str], model: str,
    temperature: float, num_predict: int, client: httpx.AsyncClient,
) -> AsyncIterator[str]:
    import json as _json

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": temperature, "num_predict": num_predict,
                    "num_ctx": LLM_NUM_CTX, "seed": LLM_SEED},
    }
    if system:
        payload["system"] = system
    async with client.stream(
        "POST", f"{OLLAMA_URL}/api/generate", json=payload, timeout=_TIMEOUT
    ) as r:
        r.raise_for_status()
        async for line in r.aiter_lines():
            if not line.strip():
                continue
            try:
                chunk = _json.loads(line)
            except ValueError:
                continue
            tok = chunk.get("response", "")
            if tok:
                yield tok
            if chunk.get("done"):
                break


# ── Groq (OpenAI-compatible chat completions) ───────────────────────────────

def _groq_messages(prompt: str, system: Optional[str]) -> list[dict]:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


async def _groq_generate(
    prompt: str, system: Optional[str], model: str,
    temperature: float, num_predict: int, client: httpx.AsyncClient,
) -> str:
    r = await client.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": model,
            "messages": _groq_messages(prompt, system),
            "temperature": temperature,
            "max_tokens": num_predict,
            "stream": False,
        },
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


async def _groq_stream(
    prompt: str, system: Optional[str], model: str,
    temperature: float, num_predict: int, client: httpx.AsyncClient,
) -> AsyncIterator[str]:
    import json as _json

    async with client.stream(
        "POST", GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": model,
            "messages": _groq_messages(prompt, system),
            "temperature": temperature,
            "max_tokens": num_predict,
            "stream": True,
        },
        timeout=_TIMEOUT,
    ) as r:
        r.raise_for_status()
        async for line in r.aiter_lines():
            line = line.strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                chunk = _json.loads(data)
                tok = chunk["choices"][0]["delta"].get("content", "")
            except (ValueError, KeyError, IndexError):
                continue
            if tok:
                yield tok


# ── Public surface ──────────────────────────────────────────────────────────

async def generate(
    prompt: str,
    system: Optional[str] = None,
    temperature: float = LLM_TEMPERATURE,
    num_predict: int = 1024,
    client: Optional[httpx.AsyncClient] = None,
) -> str:
    """One-shot generation from the active backend."""
    kind, model = _resolve()
    own = client is None
    client = client or httpx.AsyncClient()
    try:
        if kind == "groq":
            return await _groq_generate(prompt, system, model, temperature, num_predict, client)
        return await _ollama_generate(prompt, system, model, temperature, num_predict, client)
    finally:
        if own:
            await client.aclose()


async def stream_generate(
    prompt: str,
    system: Optional[str] = None,
    temperature: float = LLM_TEMPERATURE,
    num_predict: int = 1024,
    client: Optional[httpx.AsyncClient] = None,
) -> AsyncIterator[str]:
    """Token stream from the active backend."""
    kind, model = _resolve()
    own = client is None
    client = client or httpx.AsyncClient()
    try:
        if kind == "groq":
            async for tok in _groq_stream(prompt, system, model, temperature, num_predict, client):
                yield tok
        else:
            async for tok in _ollama_stream(prompt, system, model, temperature, num_predict, client):
                yield tok
    finally:
        if own:
            await client.aclose()
