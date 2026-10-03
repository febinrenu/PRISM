"""
Every model that extracts rules, behind one call.

    generate_json(system_name, prompt, *, temperature, seed) -> GenerationResult

Systems are named once here so runs, caches and the paper all refer to the
same identifiers. Local models run through Ollama with JSON-mode decoding;
Groq and Gemini through their JSON modes. Raw outputs are cached
content-addressed (cache.py), so re-running an evaluation never calls a
model twice for the same input.
"""
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from config import (
    GEMINI_API_KEY,
    GEMINI_URL,
    GROQ_API_KEY,
    GROQ_URL,
    OLLAMA_URL,
)
from pipeline.extraction import cache


@dataclass(frozen=True)
class System:
    name: str          # stable identifier used in runs and the paper
    provider: str      # ollama | groq | gemini
    model: str
    num_ctx: int = 8192
    max_tokens: int = 4096
    options: tuple = ()  # extra provider parameters, e.g. (("reasoning_effort", "low"),)


SYSTEMS: dict[str, System] = {s.name: s for s in [
    System("phi3.5", "ollama", "phi3.5:3.8b"),
    System("gemma2-2b", "ollama", "gemma2:2b"),
    System("prism-legal", "ollama", "prism-legal"),   # Phi-3.5 fine-tuned on silver data (training/)
    System("gpt-oss-120b", "groq", "openai/gpt-oss-120b"),
    # At the default (medium) reasoning effort GPT-OSS-20B can spend the whole
    # 4,096-token output budget reasoning and return no answer; the free
    # tier's 8,000 tokens/minute rules out a larger budget. Low effort fits.
    System("gpt-oss-20b", "groq", "openai/gpt-oss-20b", options=(("reasoning_effort", "low"),)),
    System("qwen3.8-27b", "groq", "qwen/qwen3.8-27b"),
    System("gemini-3.8-flash", "gemini", "gemini-3.8-flash"),
]}


@dataclass
class GenerationResult:
    text: str
    system: str
    model: str
    model_version: Optional[str]   # provider-reported version / fingerprint / digest
    cached: bool
    elapsed_ms: int
    cache_key: str


class BackendError(RuntimeError):
    pass


class RateLimited(BackendError):
    def __init__(self, message: str, retry_after: Optional[float], daily: bool):
        super().__init__(message)
        self.retry_after = retry_after
        self.daily = daily


def _rate_limited(r: httpx.Response) -> RateLimited:
    """Groq: 'Please try again in 7.66s' / retry-after; Gemini: RetryInfo
    retryDelay '31s'. A per-day quota cannot be waited out within a run."""
    text = r.text
    wait = None
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", text) or re.search(r'"retryDelay":\s*"([\d.]+)s"', text)
    if m:
        wait = (float(m.group(1) or 0) * 60 + float(m.group(2))) if m.re.groups == 2 else float(m.group(1))
    elif r.headers.get("retry-after"):
        try:
            wait = float(r.headers["retry-after"])
        except ValueError:
            pass
    daily = bool(re.search(r"per day|PerDay|\(TPD\)|\(RPD\)", text))
    return RateLimited(f"rate limited ({r.status_code}): {text[:200]}", wait, daily)


class OfflineCacheMiss(RuntimeError):
    """PRISM_OFFLINE=1 and the output is not cached: reproduction must not
    call a model (deliberately not a BackendError, so it is never recorded as
    an extraction failure)."""


def _ollama(system: System, prompt: str, temperature: float, seed: int, timeout: float) -> tuple[str, Optional[str]]:
    r = httpx.post(f"{OLLAMA_URL}/api/generate", timeout=timeout, json={
        "model": system.model, "prompt": prompt, "stream": False, "format": "json",
        "options": {"temperature": temperature, "seed": seed, "num_ctx": system.num_ctx,
                    "num_predict": system.max_tokens},
    })
    r.raise_for_status()
    return r.json().get("response", ""), None


def _ollama_digest(model: str) -> Optional[str]:
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        for m in r.json().get("models", []):
            if m.get("name") == model:
                return m.get("digest")
    except httpx.HTTPError:
        return None
    return None


def _groq(system: System, prompt: str, temperature: float, seed: int, timeout: float) -> tuple[str, Optional[str]]:
    if not GROQ_API_KEY:
        raise BackendError("GROQ_API_KEY is not set")
    r = httpx.post(GROQ_URL, timeout=timeout, headers={"Authorization": f"Bearer {GROQ_API_KEY}"}, json={
        "model": system.model, "temperature": temperature, "seed": seed,
        "max_completion_tokens": system.max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
        **dict(system.options),
    })
    if r.status_code == 429:
        raise _rate_limited(r)
    if r.status_code == 400 and "json_validate_failed" in r.text:
        # The model's output was not valid JSON: that is the system's answer
        # (scored as a parse error), not a transport failure to retry.
        failed = r.json().get("error", {}).get("failed_generation") or ""
        return failed or "<invalid JSON>", None
    r.raise_for_status()
    body = r.json()
    return body["choices"][0]["message"]["content"], body.get("system_fingerprint")


def _gemini(system: System, prompt: str, temperature: float, seed: int, timeout: float) -> tuple[str, Optional[str]]:
    if not GEMINI_API_KEY:
        raise BackendError("GEMINI_API_KEY is not set")
    r = httpx.post(f"{GEMINI_URL}/models/{system.model}:generateContent", timeout=timeout,
                   headers={"x-goog-api-key": GEMINI_API_KEY}, json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "seed": seed, "responseMimeType": "application/json",
                             "maxOutputTokens": system.max_tokens},
    })
    if r.status_code == 429:
        raise _rate_limited(r)
    if r.status_code == 503:
        raise BackendError(f"unavailable ({r.status_code}): {r.text[:200]}")
    r.raise_for_status()
    body = r.json()
    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts), body.get("modelVersion")


_PROVIDERS = {"ollama": _ollama, "groq": _groq, "gemini": _gemini}


def generate_json(system_name: str, prompt: str, *, temperature: float = 0.0, seed: int = 0,
                  prompt_version: int = 1, timeout: float = 300.0, retries: int = 4,
                  use_cache: bool = True) -> GenerationResult:
    system = SYSTEMS[system_name]
    key = cache.key(provider=system.provider, model=system.model, prompt=prompt,
                    temperature=temperature, seed=seed, prompt_version=prompt_version,
                    options=dict(system.options) or None)
    if use_cache:
        hit = cache.get(key)
        if hit is not None:
            return GenerationResult(text=hit["text"], system=system_name, model=system.model,
                                    model_version=hit.get("model_version"), cached=True,
                                    elapsed_ms=hit.get("elapsed_ms", 0), cache_key=key)
    if os.environ.get("PRISM_OFFLINE") == "1":
        raise OfflineCacheMiss(f"{system_name}: no cached output for this prompt (offline mode)")
    last: Optional[Exception] = None
    attempt = waits = 0
    while attempt < retries:
        started = time.perf_counter()
        try:
            text, version = _PROVIDERS[system.provider](system, prompt, temperature, seed, timeout)
        except RateLimited as e:
            last = e
            if e.daily or waits >= 12:
                break
            waits += 1          # waiting out a per-minute limit is not a failed attempt
            time.sleep(min(120.0, (e.retry_after or 20.0) + 1.0))
            continue
        except (httpx.HTTPError, BackendError) as e:
            last = e
            attempt += 1
            time.sleep(min(60, 5 * 2 ** attempt))
            continue
        elapsed = int((time.perf_counter() - started) * 1000)
        if system.provider == "ollama":
            version = _ollama_digest(system.model)
        cache.put(key, {"text": text, "system": system_name, "model": system.model, "options": dict(system.options),
                        "model_version": version, "elapsed_ms": elapsed,
                        "temperature": temperature, "seed": seed, "prompt_version": prompt_version})
        return GenerationResult(text=text, system=system_name, model=system.model, model_version=version,
                                cached=False, elapsed_ms=elapsed, cache_key=key)
    raise BackendError(f"{system_name}: failed after {retries} attempts: {last}")
