from __future__ import annotations

import httpx
from typing import List, Dict, Any


class LMStudioEmbeddings:
    def __init__(self, base_url: str, model: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def embed(self, texts: List[str]) -> List[List[float]]:
        url = f"{self.base_url}/v1/embeddings"
        payload: Dict[str, Any] = {"model": self.model, "input": texts}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            # OpenAI-compatible: { data: [ { embedding: [...] }, ... ] }
            return [item["embedding"] for item in data.get("data", [])]


class LMStudioChat:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.1, max_tokens: int = 1024) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            # prevent chain-of-thought like outputs; model-specific but we can suggest via system
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            choices = data.get("choices", [])
            if not choices:
                return ""
            return choices[0].get("message", {}).get("content", "")

