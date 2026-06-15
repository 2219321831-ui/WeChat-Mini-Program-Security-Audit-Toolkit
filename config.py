#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Centralized configuration for the WeChat Mini-Program Security Audit Toolkit.

All sensitive values (signing key, API base URL, activity/institution IDs) are
loaded from environment variables or a .env file.  Never hard-code secrets in
individual scripts — import them from here instead.

Usage in scripts:
    from config import SIGN_KEY, API_BASE, DEFAULT_ACT, DEFAULT_CUS
"""

import os
import sys

# ---------------------------------------------------------------------------
# .env loader (lightweight, no third-party dependency)
# ---------------------------------------------------------------------------

def _load_dotenv(path: str = ".env") -> None:
    """Read a simple KEY=VALUE .env file into os.environ (no overwrite)."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            os.environ.setdefault(key, value)


_load_dotenv()

# ---------------------------------------------------------------------------
# Secrets — MUST be set via environment or .env in production
# ---------------------------------------------------------------------------

SIGN_KEY: str = os.environ.get("WXMINI_SIGN_KEY", "")
"""API signing key extracted from the mini-program frontend source."""

API_BASE: str = os.environ.get(
    "WXMINI_API_BASE", "https://wxmini.api.bjadks.com/"
)
"""Production API base URL."""

# ---------------------------------------------------------------------------
# Default activity / institution parameters
# ---------------------------------------------------------------------------

DEFAULT_ACT: int = int(os.environ.get("WXMINI_ACT_ID", "0"))
DEFAULT_CUS: int = int(os.environ.get("WXMINI_CUS_ID", "0"))

# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

def require_sign_key() -> str:
    """Return SIGN_KEY or abort with a helpful message."""
    if not SIGN_KEY:
        print(
            "[ERROR] WXMINI_SIGN_KEY is not set.\n"
            "        Copy .env.example to .env and fill in the signing key.\n"
            "        Or: export WXMINI_SIGN_KEY='your_key_here'",
            file=sys.stderr,
        )
        sys.exit(1)
    return SIGN_KEY
