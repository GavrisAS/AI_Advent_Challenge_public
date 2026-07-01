"""Локальные embedding backends для индексации и retrieval."""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request
from hashlib import sha256
from typing import Protocol, cast

TOKEN_RE = re.compile(r"[\w-]+", re.UNICODE)


class EmbeddingBackend(Protocol):
    name: str
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbeddingBackend:
    """Deterministic feature hashing для тестов, не quality embedding model."""

    name = "hash"

    def __init__(self, dimension: int = 128) -> None:
        if dimension <= 0:
            raise ValueError("Hash embedding dimension must be positive")
        self.dimension = dimension
        self.model = f"feature-hash-{dimension}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in TOKEN_RE.findall(text.casefold()):
                digest = sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:8], "big") % self.dimension
                sign = 1.0 if digest[8] & 1 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(value * value for value in vector))
            vectors.append([value / norm for value in vector] if norm else vector)
        return vectors


class OllamaEmbeddingBackend:
    name = "ollama"

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 120.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request(self, endpoint: str, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.base_url}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RuntimeError(
                f"Ollama is unavailable at {self.base_url}. Start Ollama and pull model "
                f"'{self.model}'."
            ) from error

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            payload = self._request("/api/embed", {"model": self.model, "input": texts})
            embeddings = payload.get("embeddings")
            if not isinstance(embeddings, list):
                raise RuntimeError("Ollama /api/embed response has no embeddings array")
            vectors = cast(list[list[float | int]], embeddings)
            return [[float(value) for value in vector] for vector in vectors]
        except urllib.error.HTTPError as error:
            if error.code != 404:
                detail = error.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Ollama embedding request failed ({error.code}): {detail}. "
                    f"Check that model '{self.model}' is installed."
                ) from error

        vectors: list[list[float]] = []
        for text in texts:
            try:
                payload = self._request("/api/embeddings", {"model": self.model, "prompt": text})
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Ollama embedding request failed ({error.code}): {detail}. "
                    f"Check that model '{self.model}' is installed."
                ) from error
            embedding = payload.get("embedding")
            if not isinstance(embedding, list):
                raise RuntimeError("Ollama legacy /api/embeddings response has no embedding")
            vector = cast(list[float | int], embedding)
            vectors.append([float(value) for value in vector])
        return vectors
