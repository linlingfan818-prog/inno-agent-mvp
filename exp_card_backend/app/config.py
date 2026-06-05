from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import yaml


BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(os.getenv("APP_CONFIG", BASE_DIR / "config.yaml"))


class Settings:
    def __init__(self) -> None:
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"Config file not found: {CONFIG_PATH}. Copy config.example.yaml to config.yaml first."
            )

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg: dict[str, Any] = yaml.safe_load(f) or {}

        llm = cfg.get("llm", {})
        server = cfg.get("server", {})
        storage = cfg.get("storage", {})
        parser = cfg.get("parser", {})

        self.app_name: str = cfg.get("app_name", "Innovation Experiment Card")
        self.debug: bool = bool(cfg.get("debug", True))

        self.api_key: str = os.getenv("OPENAI_API_KEY", llm.get("api_key", ""))
        self.base_url: str | None = os.getenv("OPENAI_BASE_URL", llm.get("base_url"))
        self.chat_model: str = os.getenv("OPENAI_MODEL", llm.get("model", "Default"))
        self.vision_model: str = os.getenv("OPENAI_VISION_MODEL", llm.get("vision_model", self.chat_model))
        self.timeout_seconds: int = int(llm.get("timeout_seconds", 120))
        self.max_retries: int = int(llm.get("max_retries", 2))
        self.temperature: float = float(llm.get("temperature", 0.2))
        self.support_image_input: bool = bool(llm.get("support_image_input", False))

        self.host: str = str(server.get("host", "127.0.0.1"))
        self.port: int = int(server.get("port", 8088))
        self.frontend_origin: str = str(server.get("frontend_origin", "http://127.0.0.1:5173"))

        self.max_upload_mb: int = int(storage.get("max_upload_mb", 20))
        self.data_dir: Path = BASE_DIR / storage.get("data_dir", "data")
        self.sessions_dir: Path = self.data_dir / "sessions"
        self.docs_dir: Path = self.data_dir / "docs"
        self.uploads_dir: Path = self.data_dir / "uploads"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)

        self.default_experiment_days: int = int(parser.get("default_experiment_days", 14))
        self.default_interview_sample_size: int = int(parser.get("default_interview_sample_size", 10))


settings = Settings()
