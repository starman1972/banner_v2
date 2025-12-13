from __future__ import annotations

from openai import OpenAI

from utils import get_secret

_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = get_secret("OPENAI_API_KEY", required=True)
        _client = OpenAI(api_key=api_key)
    return _client

