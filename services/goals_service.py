# services/goals_service.py
import math
from typing import Dict, Any, List, Optional

from utils.advanced_data_analyst import AdvancedDataAnalyst

analyst = AdvancedDataAnalyst()

PLATFORM_ALIASES = {
    "ga4": "google_analytics",
    "googleanalytics": "google_analytics",
    "google_analytics": "google_analytics",
    "instagram": "instagram",
    "facebook": "facebook",
    "linkedin": "linkedin",
}

KPI_COLUMN_MAP = {
    "instagram": {
        "followers": "instagram_followers",
        "reach": "instagram_reach",
        "impressions": "instagram_views",
    },
    "facebook": {
        "followers": "facebook_followers",
        "reach": "facebook_reach",
        "impressions": "facebook_impressions",
    },
    "linkedin": {
        "followers": "linkedin_followers",
        "impressions": "linkedin_impressions",
    },
    "google_analytics": {
        "impressions": "google_analytics_impressions",
        "traffic_direct": "google_analytics_traffic_direct",
        "traffic_organic_search": "google_analytics_traffic_organic_search",
        "traffic_organic_social": "google_analytics_traffic_organic_social",
        "search_volume": "google_analytics_search_volume",
    },
}

def _normalize_platform(platform_name: str) -> str:
    return PLATFORM_ALIASES.get(str(platform_name or "").strip().lower(), str(platform_name or "").strip().lower())

def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None

def _extract_actual_from_summary(summary: Dict[str, Any], platform: str, kpi_key: str) -> Optional[float]:
    column_name = KPI_COLUMN_MAP.get(platform, {}).get(kpi_key)
    if not column_name:
        return None

    kpis = (summary or {}).get("kpis", {}) or {}
    metric_data = kpis.get(column_name) or {}

    if not metric_data:
        return None

    # Para follower/reach/impressions, usar média do período como fallback padrão
    # Se depois você quiser usar último valor do período, aí precisa expor isso no summary.
    for key in ("mean", "median", "p95", "sum"):
        if metric_data.get(key) is not None:
            return _safe_float(metric_data.get(key))

    return None

def _score_single_kpi(actual: Optional[float], baseline: Optional[float], target: Optional[float]) -> Optional[float]:
    if actual is None or baseline is None or target is None:
        return None

    if math.isclose(target, baseline):
        return 100.0 if math.isclose(actual, target) else 0.0

    # Meta de crescimento
    if target > baseline:
        progress = (actual - baseline) / (target - baseline)
    else:
        # Meta de redução
        progress = (baseline - actual) / (baseline - target)

    progress = max(0.0, min(progress, 1.0))
    return round(progress * 100, 2)

def _build_kpi_results(summary: Dict[str, Any], platform: str, kpis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []

    for item in kpis or []:
        kpi_key = item.get("kpi")
        label = item.get("label") or kpi_key
        baseline = _safe_float(item.get("baseline"))
        target = _safe_float(item.get("target"))
        actual = _extract_actual_from_summary(summary, platform, kpi_key)
        score = _score_single_kpi(actual, baseline, target)

        results.append({
            "kpi": kpi_key,
            "label": label,
            "baseline": baseline,
            "target": target,
            "actual": actual,
            "score": score,
            "achieved": bool(score is not None and score >= 100.0),
            "measurable": actual is not None and baseline is not None and target is not None
        })

    return results

def _compute_goal_score(kpi_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    measurable = [k for k in kpi_results if k.get("score") is not None]

    if not measurable:
        return {
            "achieved": False,
            "achieved_score": 0,
            "measurable_count": 0
        }

    avg_score = sum(float(k["score"]) for k in measurable) / len(measurable)
    achieved = all(float(k["score"]) >= 100.0 for k in measurable)

    return {
        "achieved": achieved,
        "achieved_score": round(avg_score),
        "measurable_count": len(measurable)
    }

def _build_goal_text(payload: Dict[str, Any], narrative: str, kpi_results: List[Dict[str, Any]], score_data: Dict[str, Any]) -> str:
    title = payload.get("title") or "Meta"
    descricao = payload.get("descricao") or "-"
    data_inicio = payload.get("data_inicio") or "-"
    data_fim = payload.get("data_fim") or "-"

    lines = []
    lines.append("1) Resumo executivo")
    lines.append(
        f'A meta "{title}" foi avaliada com base nos dados reais do período de {data_inicio} até {data_fim}. '
        f'{descricao}'
    )
    lines.append("")
    lines.append(narrative.strip() if narrative else "Não foi possível gerar a narrativa detalhada do período.")
    lines.append("")
    lines.append("2) Avaliação dos KPIs")

    if not kpi_results:
        lines.append("- Nenhum KPI foi informado para esta meta.")
    else:
        for item in kpi_results:
            label = item["label"]
            baseline = item["baseline"]
            target = item["target"]
            actual = item["actual"]
            score = item["score"]

            if score is None:
                lines.append(
                    f"- {label}: baseline={baseline}, meta={target}, realizado=indisponível no schema atual do motor de análise."
                )
            else:
                status = "atingiu" if item["achieved"] else "não atingiu"
                lines.append(
                    f"- {label}: baseline={baseline}, meta={target}, realizado={round(actual, 2) if actual is not None else actual}, {status} ({round(score, 2)}%)."
                )

    lines.append("")
    lines.append("3) Conclusão")
    lines.append(
        f"Score final da meta: {score_data['achieved_score']}/100. "
        f"Conclusão geral: {'meta atingida' if score_data['achieved'] else 'meta não atingida integralmente'}."
    )

    lines.append("")
    lines.append("4) Recomendações práticas")
    lines.append("- Reforce as alavancas que sustentaram os melhores momentos do período.")
    lines.append("- Revise os pontos de queda ou estabilidade identificados na evolução temporal.")
    lines.append("- Reavalie os KPIs sem mensuração automática para alinhá-los ao schema disponível ou expandir a coleta.")
    lines.append("- Na próxima meta, mantenha target, baseline e indicador operacional diretamente conectados aos dados do banco.")

    return "\n".join(lines).strip()

def generate_goal_analysis(payload: Dict[str, Any]) -> Dict[str, Any]:
    platform = _normalize_platform(payload.get("platform_name"))
    platforms = payload.get("platforms") or [platform]

    analysis_query = payload.get("analysis_query") or (
        f'Avalie a meta "{payload.get("title")}" usando os dados reais do período, '
        f'explique a evolução do desempenho e conclua se a meta foi atingida.'
    )

    analysis_resp = analyst.run_analysis({
        "agency_id": str(payload["agency_id"]),
        "client_id": str(payload["client_id"]),
        "platforms": platforms,
        "analysis_type": payload.get("analysis_type") or "general",
        "analysis_focus": payload.get("analysis_focus") or "panorama",
        "start_date": payload.get("data_inicio"),
        "end_date": payload.get("data_fim"),
        "output_format": payload.get("output_format") or "detalhado",
        "analysis_query": analysis_query,
        "bilingual": True,
        "granularity": "detalhada",
        "voice_profile": "CMO",
        "decision_mode": "narrativa",
        "narrative_style": "SCQA",
    })

    summary = analysis_resp.get("summary") or {}
    narrative = analysis_resp.get("result") or ""

    kpi_results = _build_kpi_results(summary, platform, payload.get("kpis") or [])
    score_data = _compute_goal_score(kpi_results)

    analysis_text = _build_goal_text(payload, narrative, kpi_results, score_data)

    return {
        "analysis_text": analysis_text,
        "achieved": score_data["achieved"],
        "achieved_score": score_data["achieved_score"],
        "summary": summary,
        "kpi_results": kpi_results
    }

def generate_goal_suggestions(payload: Dict[str, Any]) -> Dict[str, Any]:
    # mantém como estava hoje
    from openai import OpenAI
    import os
    import json
    from utils.prompts.goals_prompts import GOAL_SUGGESTIONS_SYSTEM

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    resp = client.chat.completions.create(
        model="gpt-5.4",
        messages=[
            {"role": "system", "content": GOAL_SUGGESTIONS_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
    )

    text = resp.choices[0].message.content.strip()

    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
        raise