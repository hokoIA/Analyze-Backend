from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Dict, Mapping, Optional


def _env_text(env: Mapping[str, str], key: str, default: str) -> str:
    value = env.get(key)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_float(env: Mapping[str, str], key: str, default: float) -> float:
    value = env.get(key)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_optional_float(env: Mapping[str, str], key: str) -> Optional[float]:
    value = env.get(key)
    if value is None or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class LLMConfig:
    analysis_model: str = "gpt-5.4"
    analysis_presence_penalty: float = 0.1
    analysis_frequency_penalty: float = 0.1
    analysis_temperature: Optional[float] = None
    chat_model: str = "gpt-4o"
    chat_temperature: float = 0.3
    goals_model: str = "gpt-5.4"

    def analysis_chat_openai_kwargs(self, api_key: Optional[str]) -> Dict[str, object]:
        kwargs: Dict[str, object] = {
            "model": self.analysis_model,
            "presence_penalty": self.analysis_presence_penalty,
            "frequency_penalty": self.analysis_frequency_penalty,
            "api_key": api_key,
        }
        if self.analysis_temperature is not None:
            kwargs["temperature"] = self.analysis_temperature
        return kwargs


def get_llm_config(env: Mapping[str, str] = environ) -> LLMConfig:
    return LLMConfig(
        analysis_model=_env_text(env, "ANALYZE_LLM_MODEL", "gpt-5.4"),
        analysis_presence_penalty=_env_float(env, "ANALYZE_LLM_PRESENCE_PENALTY", 0.1),
        analysis_frequency_penalty=_env_float(env, "ANALYZE_LLM_FREQUENCY_PENALTY", 0.1),
        analysis_temperature=_env_optional_float(env, "ANALYZE_LLM_TEMPERATURE"),
        chat_model=_env_text(env, "CHAT_LLM_MODEL", "gpt-4o"),
        chat_temperature=_env_float(env, "CHAT_LLM_TEMPERATURE", 0.3),
        goals_model=_env_text(env, "GOALS_LLM_MODEL", "gpt-5.4"),
    )
