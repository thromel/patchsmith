"""Small shared HTTP helpers for the OpenAI client and preflight checks."""

from __future__ import annotations

import urllib.request


def open_url(request: urllib.request.Request, timeout_seconds: float) -> bytes:
    """Send ``request`` and return the raw response body."""
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()
