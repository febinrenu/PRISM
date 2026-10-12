"""
Every model that extracts rules, behind one call.

    generate_json(system_name, prompt, *, temperature, seed) -> GenerationResult

Systems are named once here so runs, caches and the paper all refer to the
same identifiers. Local models run through Ollama with JSON-mode decoding;
Groq and OpenRouter through their OpenAI-compatible JSON modes, each with a
pool of API keys used in rotation. "batch" systems are never called live:
their outputs are produced on a GPU elsewhere (Kaggle) from an exported
prompt file and imported into the cache (pipeline/extraction/batch.py). Raw outputs are cached
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
    GROQ_API_KEY,
    GROQ_API_KEYS,
    GROQ_URL,
    OLLAMA_URL,
    OPENROUTER_API_KEYS,
    OPENROUTER_URL,
)
from pipeline.extraction import cache


@dataclass(frozen=True)
class System:
    name: str          # stable identifier used in runs and the paper
    provider: str      # ollama | groq | openrouter | batch
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
    # The free tier allows Qwen3.8-27B 1,000 output tokens per minute, so an
    # answer plus hidden reasoning longer than that can never be returned
    # ("Request too large"). With reasoning off its answers fit.
    System("qwen3.8-27b", "groq", "qwen/qwen3.8-27b", options=(("reasoning_effort", "none"),)),
    # Free open-weight models from other model families, through OpenRouter
    # (pinned model ids; the ":free" routes have per-account daily limits).
    System("gemma-4-31b", "openrouter", "google/gemma-4-31b-it:free"),
    System("nemotron-3-super", "openrouter", "nvidia/nemotron-3-super-120b-a12b:free"),
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
    elif r.headers.get("x-ratelimit-reset"):
        try:                                     # OpenRouter: epoch milliseconds
            wait = max(0.0, float(r.headers["x-ratelimit-reset"]) / 1000.0 - time.time())
        except ValueError:
            pass
    daily = bool(re.search(r"per day|per-day|PerDay|\(TPD\)|\(RPD\)", text))
    return RateLimited(f"rate limited ({r.status_code}): {text[:200]}", wait, daily)


class QuotaExhausted(RuntimeError):
    """A per-day quota is used up. Deliberately not a BackendError: it stops
    the whole run instead of being recorded item by item as a failed call."""


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


class _KeyPool:
    """Rotates requests over several API keys. Limits are tracked per key and
    model: a per-minute limit cools that key down, a per-day limit retires it
    for that model; a run stops only when every key is retired."""

    def __init__(self, keys: list[str]):
        self.keys = keys
        self.next = 0
        self.cool_until: dict[tuple[str, str], float] = {}
        self.retired: set[tuple[str, str]] = set()

    def pick(self, model: str) -> str:
        while True:
            alive = [k for k in self.keys if (k, model) not in self.retired]
            if not alive:
                raise QuotaExhausted(f"{model}: daily quota exhausted on all {len(self.keys)} keys")
            now = time.time()
            n = len(self.keys)
            for j in range(n):
                k = self.keys[(self.next + j) % n]
                if (k, model) not in self.retired and self.cool_until.get((k, model), 0.0) <= now:
                    self.next = (self.next + j + 1) % n
                    return k
            time.sleep(max(0.5, min(self.cool_until.get((k, model), now) for k in alive) - now))

    def cool(self, key: str, model: str, seconds: float) -> None:
        self.cool_until[(key, model)] = time.time() + seconds

    def retire(self, key: str, model: str) -> None:
        self.retired.add((key, model))


_POOLS = {"groq": _KeyPool(GROQ_API_KEYS), "openrouter": _KeyPool(OPENROUTER_API_KEYS)}


def _groq(system: System, prompt: str, temperature: float, seed: int, timeout: float,
          api_key: Optional[str] = None) -> tuple[str, Optional[str]]:
    api_key = api_key or GROQ_API_KEY
    if not api_key:
        raise BackendError("GROQ_API_KEY is not set")
    r = httpx.post(GROQ_URL, timeout=timeout, headers={"Authorization": f"Bearer {api_key}"}, json={
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


def _openrouter(system: System, prompt: str, temperature: float, seed: int, timeout: float,
                api_key: Optional[str] = None) -> tuple[str, Optional[str]]:
    if not api_key:
        raise BackendError("OPENROUTER_API_KEYS is not set")
    r = httpx.post(OPENROUTER_URL, timeout=timeout, headers={"Authorization": f"Bearer {api_key}"}, json={
        "model": system.model, "temperature": temperature, "seed": seed,
        "max_tokens": system.max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
        **dict(system.options),
    })
    if r.status_code == 429:
        raise _rate_limited(r)
    if r.status_code in (502, 503):
        raise BackendError(f"unavailable ({r.status_code}): {r.text[:200]}")
    r.raise_for_status()
    body = r.json()
    if "error" in body:                      # OpenRouter reports upstream failures in a 200 body
        raise BackendError(f"upstream error: {str(body['error'])[:200]}")
    msg = body["choices"][0]["message"]
    return msg.get("content") or "", f"{body.get('model')}@{body.get('provider')}"


def _batch(system: System, prompt: str, temperature: float, seed: int, timeout: float) -> tuple[str, Optional[str]]:
    raise BackendError(f"{system.name} runs in batch on a GPU host: export the prompts with "
                       f"`cli batch-export`, run them, then `cli batch-import` (no live calls)")


_PROVIDERS = {"ollama": _ollama, "groq": _groq, "openrouter": _openrouter, "batch": _batch}


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
    # Configuration problems fail at once instead of through the retry loop.
    if system.provider == "batch":
        _batch(system, prompt, temperature, seed, timeout)
    if system.provider == "groq" and not GROQ_API_KEYS:
        raise BackendError("GROQ_API_KEY is not set")
    if system.provider == "openrouter" and not OPENROUTER_API_KEYS:
        raise BackendError("OPENROUTER_API_KEYS is not set")
    pool = _POOLS.get(system.provider)
    pooled = pool is not None and bool(pool.keys) and (len(pool.keys) > 1 or system.provider == "openrouter")
    while attempt < retries:
        started = time.perf_counter()
        api_key = pool.pick(system.model) if pooled else None
        try:
            extra = {"api_key": api_key} if api_key else {}
            text, version = _PROVIDERS[system.provider](system, prompt, temperature, seed, timeout, **extra)
        except RateLimited as e:
            last = e
            if pooled:
                # Another key may still have room: retire or cool this one and move on.
                if e.daily:
                    pool.retire(api_key, system.model)
                else:
                    pool.cool(api_key, system.model, min(120.0, (e.retry_after or 20.0) + 1.0))
                waits += 1
                if waits >= 12 * len(pool.keys):
                    break
                continue
            if e.daily:
                raise QuotaExhausted(f"{system_name}: daily quota exhausted: {e}") from e
            if waits >= 12:
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
