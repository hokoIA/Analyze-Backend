from __future__ import annotations

from typing import Any, Dict, List


class RAGQueryBuilder:
    def build(
        self,
        analysis_query: str,
        platforms: List[str],
        summary: Dict[str, Any],
        analysis_type: str,
        analysis_focus: str,
    ) -> str:
        parts: List[str] = []

        if analysis_query:
            parts.append(analysis_query.strip())

        analysis_type_value = (analysis_type or "descriptive").strip().lower()
        parts.append(f"tipo={analysis_type_value}")
        parts.append(f"foco={analysis_focus or 'panorama'}")

        if isinstance(summary, dict):
            meta = summary.get("meta", {}) or {}
            selected = meta.get("selected_metrics") or []
            if selected:
                parts.append("metricas-chave: " + ", ".join(selected[:6]))

            anomalies = summary.get("anomalies", {}) or {}
            hot_metrics = [metric for metric, values in anomalies.items() if values]
            if hot_metrics:
                parts.append("metricas-com-picos: " + ", ".join(hot_metrics[:6]))

        if platforms:
            parts.append("plataformas: " + ", ".join(platforms))

        return " | ".join(parts)
