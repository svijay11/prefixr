"""Configuration management."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".prefixr"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "anthropic_api_key": "",
    "openai_api_key": "",
    "deepseek_api_key": "",
    "gemini_api_key": "",
    "port": 4242,
    "prefixr_api_key": "",
    "optimizer": {
        "horizon_turns": 5,
        "summarizer_model": "claude-haiku-4-5",
        "summarizer_provider": "anthropic",
        "padding_enabled": True,
        "timestamp_scrubbing": True,
    },
}


@dataclass
class OptimizerConfig:
    horizon_turns: int = 5
    summarizer_model: str = "claude-haiku-4-5"
    summarizer_provider: str = "anthropic"
    padding_enabled: bool = True
    timestamp_scrubbing: bool = True


@dataclass
class PrefixrConfig:
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    gemini_api_key: str = ""
    port: int = 4242
    prefixr_api_key: str = ""
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> PrefixrConfig:
        config_path = path or CONFIG_PATH
        if not config_path.exists():
            return cls()
        data = json.loads(config_path.read_text())
        opt = data.get("optimizer", {})
        return cls(
            anthropic_api_key=data.get("anthropic_api_key", ""),
            openai_api_key=data.get("openai_api_key", ""),
            deepseek_api_key=data.get("deepseek_api_key", ""),
            gemini_api_key=data.get("gemini_api_key", ""),
            port=data.get("port", 4242),
            prefixr_api_key=data.get("prefixr_api_key", ""),
            optimizer=OptimizerConfig(
                horizon_turns=opt.get("horizon_turns", 5),
                summarizer_model=opt.get("summarizer_model", "claude-haiku-4-5"),
                summarizer_provider=opt.get("summarizer_provider", "anthropic"),
                padding_enabled=opt.get("padding_enabled", True),
                timestamp_scrubbing=opt.get("timestamp_scrubbing", True),
            ),
        )

    def save(self, path: Path | None = None) -> None:
        config_path = path or CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "anthropic_api_key": self.anthropic_api_key,
            "openai_api_key": self.openai_api_key,
            "deepseek_api_key": self.deepseek_api_key,
            "gemini_api_key": self.gemini_api_key,
            "port": self.port,
            "prefixr_api_key": self.prefixr_api_key,
            "optimizer": {
                "horizon_turns": self.optimizer.horizon_turns,
                "summarizer_model": self.optimizer.summarizer_model,
                "summarizer_provider": self.optimizer.summarizer_provider,
                "padding_enabled": self.optimizer.padding_enabled,
                "timestamp_scrubbing": self.optimizer.timestamp_scrubbing,
            },
        }
        config_path.write_text(json.dumps(data, indent=2))

    def get_api_key(self, provider: str) -> str:
        keys = {
            "anthropic": self.anthropic_api_key,
            "openai": self.openai_api_key,
            "deepseek": self.deepseek_api_key,
            "gemini": self.gemini_api_key,
        }
        return keys.get(provider, "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "port": self.port,
            "optimizer": {
                "horizon_turns": self.optimizer.horizon_turns,
                "summarizer_model": self.optimizer.summarizer_model,
                "summarizer_provider": self.optimizer.summarizer_provider,
                "padding_enabled": self.optimizer.padding_enabled,
                "timestamp_scrubbing": self.optimizer.timestamp_scrubbing,
            },
        }
