from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .config import settings


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def session_path(session_id: str) -> Path:
    return settings.sessions_dir / f"{session_id}.json"


def save_session(session_id: str, payload: dict[str, Any]) -> None:
    with open(session_path(session_id), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_session(session_id: str) -> dict[str, Any]:
    path = session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(f"Session not found: {session_id}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
