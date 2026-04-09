"""Embedding: single + batch, DashScope or OpenAI, with retry."""
from __future__ import annotations
import json, os, time, urllib.request, urllib.error
from config import env

DASHSCOPE_BATCH_LIMIT = 25


def _retry(fn, retries=3, backoff=1.0):
    """Simple retry with exponential backoff for transient HTTP errors."""
    for attempt in range(retries):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            raise


def _embed_dashscope(texts: list[str], api_key: str) -> list[list[float]]:
    url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
    body = json.dumps({"model": "text-embedding-v2", "input": {"texts": texts}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }, method="POST")
    def call():
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        if "output" in data and "embeddings" in data["output"]:
            return [e["embedding"] for e in data["output"]["embeddings"]]
        raise RuntimeError(data.get("message", str(data)))
    return _retry(call)


def _embed_openai(texts: list[str], api_key: str, base_url: str | None) -> list[list[float]]:
    base = (base_url or "https://api.openai.com/v1").rstrip("/")
    url = base + "/embeddings"
    body = json.dumps({"input": texts, "model": "text-embedding-ada-002"}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }, method="POST")
    def call():
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return [d["embedding"] for d in data["data"]]
    return _retry(call)


def get_embedding(text: str) -> list[float]:
    """Single text -> 1536-dim vector."""
    vecs = get_embeddings_batch([text])
    return vecs[0]


def get_embeddings_batch(texts: list[str], batch_size: int = DASHSCOPE_BATCH_LIMIT) -> list[list[float]]:
    """Batch embedding. Returns list aligned with input order."""
    if not texts:
        return []
    api_key = env("DASHSCOPE_API_KEY")
    if api_key:
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            results.extend(_embed_dashscope(batch, api_key))
        return results
    api_key = env("OPENAI_API_KEY")
    if api_key:
        base_url = env("OPENAI_API_BASE") or env("EMBEDDING_API_BASE")
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            results.extend(_embed_openai(batch, api_key, base_url))
        return results
    raise RuntimeError("Set DASHSCOPE_API_KEY or OPENAI_API_KEY for embeddings.")
