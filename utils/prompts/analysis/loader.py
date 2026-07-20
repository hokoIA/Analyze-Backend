from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Optional


PROMPT_ROOT = Path(__file__).resolve().parent


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _resolve_prompt_path(relative_path: str) -> Path:
    candidate = (PROMPT_ROOT / relative_path).resolve()
    if not candidate.is_relative_to(PROMPT_ROOT):
        raise ValueError(f"Invalid prompt path outside prompt root: {relative_path}")
    if candidate.suffix != ".md":
        raise ValueError(f"Prompt blocks must be markdown files: {relative_path}")
    return candidate


@lru_cache(maxsize=128)
def load_prompt_block(relative_path: str) -> str:
    path = _resolve_prompt_path(relative_path)
    return path.read_text(encoding="utf-8").strip()


def render_prompt_block(
    relative_path: str,
    variables: Optional[Mapping[str, Any]] = None,
) -> str:
    template = load_prompt_block(relative_path)
    if not variables:
        return template
    safe_variables = _SafeFormatDict({
        key: "" if value is None else str(value)
        for key, value in variables.items()
    })
    return template.format_map(safe_variables).strip()

