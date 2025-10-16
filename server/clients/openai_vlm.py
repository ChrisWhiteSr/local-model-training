from __future__ import annotations

import base64
import os
from typing import Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class OpenAIVLM:
    def __init__(self, api_key: Optional[str], model: str = "gpt-5-mini", timeout: float = 60.0):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.timeout = timeout
        self._client = None
        if OpenAI and self.api_key:
            self._client = OpenAI(api_key=self.api_key)

    async def ocr_image(self, image_bytes: bytes) -> str:
        if not self._client:
            return ""
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:image/png;base64,{b64}"
        # Use Chat Completions with image input; request plain text transcription in reading order
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Transcribe the image content into plain UTF-8 text in correct reading order. Do not add commentary."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please transcribe this page as plain text."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=0.0,
        )
        choices = resp.choices or []
        if not choices:
            return ""
        return choices[0].message.content or ""

