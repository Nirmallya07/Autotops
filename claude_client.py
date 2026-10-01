"""
Thin wrapper around the Anthropic SDK. Keeping this separate means
graph.py doesn't need to know *how* we talk to Claude, just that it can
call `ask_claude(system, user_prompt)` and get text back.
"""

import os
from anthropic import Anthropic

_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def ask_claude(system: str, user_prompt: str, max_tokens: int = 1024) -> str:
    """Single-turn call. For multi-turn reasoning inside a node, extend this
    to accept a message history instead of a single user_prompt."""
    client = get_client()
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # response.content is a list of blocks; we only expect text for now
    return "".join(block.text for block in response.content if block.type == "text")
