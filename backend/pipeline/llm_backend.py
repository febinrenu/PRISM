"""
Phase 3 — unified LLM backend abstraction (Module D/E/F).

A single async surface (`generate` / `stream_generate`) that dispatches to the
configured backend so RAG, chat, and reasoning code never hard-code Ollama:

    LLM_BACKEND=ollama            → local Phi-3.5-mini (dev default)
    LLM_BACKEND=ollama_finetuned  → local QLoRA-merged model (Module E)
    LLM_BACKEND=groq              → Groq cloud (GROQ_MODEL, default openai/gpt-oss-120b)

If the configured backend fails (Ollama stopped, the hosted model rate-limited or
without a key) the other one is tried when it is usable, so a demo does not end on a
network error. LLM_FALLBACK=0 switches that off. Hosted calls rotate over every key
in GROQ_API_KEYS and move to the next on a 401/403/429.

The structured causal extractor (`llm_extractor.py`) keeps its own dedicated
Ollama call — it needs `format:"json"` + a warmup and is deliberately pinned to
the local Phi-3.5 for reproducibility of Phase 2 results. This module serves the
conversational / free-form path where a cloud fallback is useful when deployed.
"""
import asyncio
import itertools
from typing import AsyncIterator, Optional

import httpx

from config import (
    GROQ_API_KEY,
    GROQ_API_KEYS,
    GROQ_MODEL,
    GROQ_URL,
    LLM_BACKEND,
    LLM_FALLBACK,
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

# How long Ollama keeps the model in memory after a call. Its default (5 minutes) means a
# question after a pause pays the model's load time again.
KEEP_ALIVE = "30m"


async def warm() -> bool:
    """Load the local model now, so the first question does not wait for it. Returns
    whether the model answered; a stopped server or a hosted-only setup is not an error."""
    kind, model = _resolve()
    if kind != "ollama":
        return False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{OLLAMA_URL}/api/generate", timeout=httpx.Timeout(180.0, connect=3.0),
                                  json={"model": model, "prompt": "", "keep_alive": KEEP_ALIVE,
                                        "options": {"num_ctx": LLM_NUM_CTX}})
            return r.status_code == 200
    except Exception:
        return False


def _resolve() -> tuple[str, str]:
    """Return (backend, model) for the active configuration."""
    backend = LLM_BACKEND
    if backend == "groq":
        return "groq", GROQ_MODEL
    if backend == "ollama_finetuned":
        return "ollama", OLLAMA_FT_MODEL
    return "ollama", OLLAMA_MODEL


def _groq_ready() -> bool:
    return bool(GROQ_API_KEYS)


def chain() -> list[tuple[str, str]]:
    """The backends to try, in order: the configured one, then the other when it is
    usable (hosted needs a key; local needs only a running server). With
    LLM_FALLBACK off, only the configured one."""
    primary = _resolve()
    out = [primary]
    if LLM_FALLBACK:
        if primary[0] == "groq":
            out.append(("ollama", OLLAMA_MODEL))
        elif _groq_ready():
            out.append(("groq", GROQ_MODEL))
    if primary[0] == "groq" and not _groq_ready() and len(out) > 1:
        out.reverse()           # no key: do not wait on a call that cannot succeed
    return out


def active_backend() -> dict:
    """Status descriptor for /health, admin dashboard, and chat UI."""
    kind, model = _resolve()
    order = chain()
    return {
        "backend": LLM_BACKEND,
        "kind": kind,
        "model": model,
        "cloud": kind == "groq",
        "configured": _groq_ready() if kind == "groq" else True,
        "fallback": ({"kind": order[1][0], "model": order[1][1]} if len(order) > 1 else None),
    }


def friendly_error(exc: BaseException, kind: str = "") -> str:
    """What went wrong with a model call, in words a user can act on."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 429:
            return "the hosted model is rate-limited right now"
        if code in (401, 403):
            return "the hosted model rejected the API key"
        if code >= 500:
            return f"the model server returned an error ({code})"
        return f"the model server refused the request ({code})"
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        if kind == "ollama":
            return "Ollama is not running (start it with `ollama serve`)"
        return "the hosted model could not be reached"
    if isinstance(exc, httpx.ReadTimeout):
        return "the model took too long to answer"
    return str(exc) or exc.__class__.__name__


# ── Ollama ────────────────────────────────────────────────────────────────

async def _ollama_generate(
    prompt: str, system: Optional[str], model: str,
    temperature: float, num_predict: int, client: httpx.AsyncClient,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
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
        "keep_alive": KEEP_ALIVE,
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


_key_cycle = itertools.count()


def _groq_keys() -> list[str]:
    """The configured keys, starting from a rotating offset so load spreads over them."""
    keys = list(GROQ_API_KEYS)
    if len(keys) > 1:
        k = next(_key_cycle) % len(keys)
        keys = keys[k:] + keys[:k]
    return keys


async def _groq_generate(
    prompt: str, system: Optional[str], model: str,
    temperature: float, num_predict: int, client: httpx.AsyncClient, key: str = GROQ_API_KEY,
) -> str:
    r = await client.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}"},
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
    temperature: float, num_predict: int, client: httpx.AsyncClient, key: str = GROQ_API_KEY,
) -> AsyncIterator[str]:
    import json as _json

    async with client.stream(
        "POST", GROQ_URL,
        headers={"Authorization": f"Bearer {key}"},
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

_RETRY_KEY = (401, 403, 429)     # another key may work; a server error will not improve
MAX_RATE_WAIT_S = 8.0            # the longest a rate-limited call waits before trying the keys again


def _retry_after(e: httpx.HTTPStatusError) -> float:
    """Seconds the server asks us to wait after a 429, bounded: a demo does not wait a minute."""
    try:
        return min(MAX_RATE_WAIT_S, max(1.0, float(e.response.headers.get("retry-after", "3"))))
    except ValueError:
        return 3.0


async def _generate_on(kind, model, prompt, system, temperature, num_predict, client) -> str:
    if kind != "groq":
        return await _ollama_generate(prompt, system, model, temperature, num_predict, client)
    last: Optional[Exception] = None
    for attempt in range(2):                    # every key, then once more after a short wait
        for key in _groq_keys() or [GROQ_API_KEY]:
            try:
                return await _groq_generate(prompt, system, model, temperature, num_predict, client, key)
            except httpx.HTTPStatusError as e:
                last = e
                if e.response.status_code not in _RETRY_KEY:
                    raise
        if attempt == 0 and isinstance(last, httpx.HTTPStatusError) and last.response.status_code == 429:
            await asyncio.sleep(_retry_after(last))
        else:
            break
    raise last or RuntimeError("no hosted-model key is configured")


async def _stream_on(kind, model, prompt, system, temperature, num_predict, client) -> AsyncIterator[str]:
    if kind != "groq":
        async for tok in _ollama_stream(prompt, system, model, temperature, num_predict, client):
            yield tok
        return
    last: Optional[Exception] = None
    for attempt in range(2):
        for key in _groq_keys() or [GROQ_API_KEY]:
            started = False
            try:
                async for tok in _groq_stream(prompt, system, model, temperature, num_predict, client, key):
                    started = True
                    yield tok
                return
            except httpx.HTTPStatusError as e:
                last = e
                if started or e.response.status_code not in _RETRY_KEY:
                    raise
        if attempt == 0 and isinstance(last, httpx.HTTPStatusError) and last.response.status_code == 429:
            await asyncio.sleep(_retry_after(last))
        else:
            break
    raise last or RuntimeError("no hosted-model key is configured")


async def generate(
    prompt: str,
    system: Optional[str] = None,
    temperature: float = LLM_TEMPERATURE,
    num_predict: int = 1024,
    client: Optional[httpx.AsyncClient] = None,
    trace: Optional[dict] = None,
) -> str:
    """One-shot generation from the active backend, falling back to the other one
    when it fails. `trace`, if given, is filled with which backend answered."""
    own = client is None
    client = client or httpx.AsyncClient()
    failures: list[str] = []
    try:
        order = chain()
        for i, (kind, model) in enumerate(order):
            try:
                text = await _generate_on(kind, model, prompt, system, temperature, num_predict, client)
            except Exception as e:
                failures.append(f"{kind}: {friendly_error(e, kind)}")
                if i == len(order) - 1:
                    raise RuntimeError("; ".join(failures)) from e
                continue
            if trace is not None:
                trace.update(backend=kind, model=model, fell_back=i > 0, reason="; ".join(failures) or None)
            return text
        raise RuntimeError("no model backend is configured")
    finally:
        if own:
            await client.aclose()


async def stream_generate(
    prompt: str,
    system: Optional[str] = None,
    temperature: float = LLM_TEMPERATURE,
    num_predict: int = 1024,
    client: Optional[httpx.AsyncClient] = None,
    trace: Optional[dict] = None,
) -> AsyncIterator[str]:
    """Token stream from the active backend. If it fails before producing a token,
    the other backend is tried; once tokens have flowed, a failure is raised (the
    caller already has a partial answer). `trace` records which backend answered."""
    own = client is None
    client = client or httpx.AsyncClient()
    failures: list[str] = []
    try:
        order = chain()
        for i, (kind, model) in enumerate(order):
            started = False
            try:
                async for tok in _stream_on(kind, model, prompt, system, temperature, num_predict, client):
                    if not started:
                        started = True
                        if trace is not None:
                            trace.update(backend=kind, model=model, fell_back=i > 0,
                                         reason="; ".join(failures) or None)
                    yield tok
                if started:
                    return
                failures.append(f"{kind}: no answer")        # an empty stream is a failure too
            except Exception as e:
                if started:
                    raise
                failures.append(f"{kind}: {friendly_error(e, kind)}")
            if i == len(order) - 1:
                raise RuntimeError("; ".join(failures))
    finally:
        if own:
            await client.aclose()
