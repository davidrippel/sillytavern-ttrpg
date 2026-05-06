from __future__ import annotations

import base64
import os
import re
from typing import Any

import httpx

from common.env import load_project_dotenv
from common.retrying import retry_call
from common.settings import (
    get_openrouter_api_url,
    get_openrouter_max_retries,
    get_openrouter_timeout_seconds,
)


class ImageGenError(RuntimeError):
    pass


_DATA_URL_RE = re.compile(r"^data:image/[a-zA-Z0-9.+-]+;base64,(?P<payload>.+)$", re.DOTALL)


def resolve_size(dimension: int, aspect_ratio: str) -> tuple[int, int]:
    """Resolve a long-edge dimension and W:H ratio into concrete (width, height).

    The long edge maps to `dimension`; the short edge is rounded to the nearest
    multiple of 8 to keep image models happy.
    """
    try:
        w_part, h_part = aspect_ratio.split(":", 1)
        w_ratio = float(w_part)
        h_ratio = float(h_part)
    except (ValueError, AttributeError) as exc:
        raise ImageGenError(f"invalid IMAGE_GEN_ASPECT_RATIO {aspect_ratio!r}; expected W:H") from exc
    if w_ratio <= 0 or h_ratio <= 0:
        raise ImageGenError(f"aspect ratio components must be positive, got {aspect_ratio!r}")

    if w_ratio >= h_ratio:
        width = dimension
        height = int(round(dimension * (h_ratio / w_ratio) / 8) * 8)
    else:
        height = dimension
        width = int(round(dimension * (w_ratio / h_ratio) / 8) * 8)
    return max(width, 8), max(height, 8)


def _extract_image_bytes(response: dict[str, Any]) -> bytes:
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError) as exc:
        raise ImageGenError(f"unexpected OpenRouter response shape: {response}") from exc

    images = message.get("images") or []
    for image in images:
        url = (image.get("image_url") or {}).get("url") if isinstance(image, dict) else None
        if isinstance(url, str):
            match = _DATA_URL_RE.match(url)
            if match:
                return base64.b64decode(match.group("payload"))

    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                url = (part.get("image_url") or {}).get("url") or part.get("url")
                if isinstance(url, str):
                    match = _DATA_URL_RE.match(url)
                    if match:
                        return base64.b64decode(match.group("payload"))
    elif isinstance(content, str):
        match = _DATA_URL_RE.match(content.strip())
        if match:
            return base64.b64decode(match.group("payload"))

    raise ImageGenError(f"no image data found in response: {response}")


class OpenRouterImageClient:
    def __init__(self, *, api_key: str | None = None) -> None:
        load_project_dotenv()
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ImageGenError("OPENROUTER_API_KEY is not set. Add it to your .env.")
        self.api_url = get_openrouter_api_url()
        self.timeout_seconds = get_openrouter_timeout_seconds()
        self.max_retries = get_openrouter_max_retries()

    def generate(self, *, model: str, prompt: str, width: int, height: int) -> bytes:
        size_hint = f"Render at {width}x{height} pixels ({width}:{height} aspect)."
        full_prompt = f"{prompt}\n\n{size_hint}"
        payload: dict[str, Any] = {
            "model": model,
            "modalities": ["image", "text"],
            "messages": [
                {"role": "user", "content": full_prompt},
            ],
        }

        def _request() -> dict[str, Any]:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        response = retry_call(_request, attempts=self.max_retries, base_delay=1.0, exceptions=(httpx.HTTPError,))
        return _extract_image_bytes(response)
