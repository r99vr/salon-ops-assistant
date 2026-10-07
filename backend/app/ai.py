"""عميل OpenRouter: يرسل نص + صورة ويرجع JSON."""
import base64
import json
import logging
import mimetypes
import re
from pathlib import Path

import httpx

from .config import get_settings

log = logging.getLogger("salon.ai")
settings = get_settings()


class AIError(Exception):
    pass


def _image_part(path: Path) -> dict:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def parse_json(text: str) -> dict:
    """يقبل JSON صافي أو داخل ```json``` أو مع كلام قبله وبعده."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIError(f"رد النموذج مو JSON صالح: {e}") from e


def chat_json(system: str, user_text: str, image_path: Path | None = None, timeout: float = 45) -> dict:
    if not settings.ai_enabled:
        raise AIError("لا يوجد مفتاح OpenRouter")
    content: list[dict] = [{"type": "text", "text": user_text}]
    if image_path and image_path.exists():
        content.append(_image_part(image_path))
    payload = {
        "model": settings.openrouter_model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": settings.public_base_url,
        "X-Title": "Salon Ops Assistant",
    }
    try:
        r = httpx.post(
            f"{settings.openrouter_base_url}/chat/completions", json=payload, headers=headers, timeout=timeout
        )
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"] or ""
    except (httpx.HTTPError, KeyError, IndexError) as e:
        log.warning("OpenRouter فشل: %s", e)
        raise AIError(str(e)) from e
    usage = data.get("usage") or {}
    log.info("AI tokens in=%s out=%s", usage.get("prompt_tokens"), usage.get("completion_tokens"))
    return parse_json(text)
