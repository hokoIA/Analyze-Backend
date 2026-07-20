from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Mapping, Optional


SENSITIVE_KEY_RE = re.compile(
    r"(token|secret|password|senha|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|cookie)",
    re.IGNORECASE,
)
SENSITIVE_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9_\-]{12,}|EAA[A-Za-z0-9_\-]{20,}|Bearer\s+[A-Za-z0-9_\-.]+)",
    re.IGNORECASE,
)


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "sim"}


class PromptDebugLogger:
    def __init__(self, env: Mapping[str, str] = os.environ):
        self.enabled = _truthy(env.get("ANALYZE_DEBUG_PROMPT_LOGS"))
        self.full = not _truthy(env.get("ANALYZE_DEBUG_PROMPT_SUMMARY_ONLY"))
        self.chunk_size = self._env_int(env.get("ANALYZE_DEBUG_PROMPT_CHUNK_SIZE"), 12000)
        self.max_chars = self._env_int(env.get("ANALYZE_DEBUG_PROMPT_MAX_CHARS"), 0)

    @staticmethod
    def _env_int(value: Optional[str], default: int) -> int:
        try:
            parsed = int(str(value or "").strip())
            return parsed if parsed > 0 else default
        except Exception:
            return default

    def log_json(self, event: str, payload: Any, request_id: Optional[str] = None) -> None:
        if not self.enabled:
            return
        safe_payload = self.sanitize(payload)
        if not self.full:
            safe_payload = self.compact_shape(safe_payload)
        text = json.dumps(safe_payload, ensure_ascii=False, default=str, indent=2)
        self.log_text(event, text, request_id=request_id)

    def log_text(self, event: str, text: Any, request_id: Optional[str] = None) -> None:
        if not self.enabled:
            return
        content = self.sanitize_text(str(text or ""))
        if self.max_chars and len(content) > self.max_chars:
            content = content[: self.max_chars] + "\n...[TRUNCATED_BY_ANALYZE_DEBUG_PROMPT_MAX_CHARS]..."

        chunks = self._chunks(content)
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            print(
                f"[analyze-prompt-debug] request_id={request_id or '-'} "
                f"event={event} chunk={index}/{total} at={datetime.utcnow().isoformat()}Z"
            )
            print(chunk)

    def sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            safe = {}
            for key, item in value.items():
                key_text = str(key)
                if SENSITIVE_KEY_RE.search(key_text):
                    safe[key_text] = "[REDACTED]"
                else:
                    safe[key_text] = self.sanitize(item)
            return safe
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        if isinstance(value, tuple):
            return [self.sanitize(item) for item in value]
        if isinstance(value, str):
            return self.sanitize_text(value)
        return value

    def sanitize_text(self, value: str) -> str:
        return SENSITIVE_VALUE_RE.sub("[REDACTED]", value)

    def compact_shape(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self.compact_shape(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            preview = [self.compact_shape(item) for item in value[:3]]
            return {
                "type": "list",
                "count": len(value),
                "preview": preview,
            }
        if isinstance(value, str):
            return value[:500] + ("...[truncated]" if len(value) > 500 else "")
        return value

    def _chunks(self, text: str) -> list[str]:
        size = max(self.chunk_size, 1000)
        if not text:
            return [""]
        return [text[index: index + size] for index in range(0, len(text), size)]
