from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class AnalysisPromptInput:
    platforms: List[str]
    analysis_type: str
    analysis_focus: str
    analysis_query: str
    context_text: str
    summary_json: Dict[str, Any]
    output_format: str = "detalhado"
    granularity: str = "detalhada"
    bilingual: bool = True
    voice_profile: str = "CMO"
    decision_mode: str = "decision_brief"
    narrative_style: str = "SCQA"

