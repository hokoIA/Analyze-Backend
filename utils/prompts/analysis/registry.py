from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


PLATFORM_DISPLAY = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "google_analytics": "Google Analytics",
    "linkedin": "LinkedIn",
    "meta_ads": "Meta Ads",
}

BASE_LABELS = {
    "reach": "Alcance",
    "views": "Visualizacoes",
    "impressions": "Impressoes",
    "followers": "Seguidores",
    "traffic_direct": "Trafego Direto",
    "traffic_organic_search": "Trafego - Busca Organica",
    "traffic_organic_social": "Trafego - Social Organico",
    "search_volume": "Volume de Busca",
    "investment": "Investimento",
    "frequency": "Frequencia",
    "cpm": "CPM",
    "ctr": "CTR",
    "cpc": "CPC",
    "conversations_started": "Conversas iniciadas",
    "roas": "ROAS",
    "cost_per_lead": "Custo por lead",
    "leads": "Leads",
    "posts_count": "Total de posts",
    "posts_likes": "Curtidas em posts",
    "posts_comments": "Comentarios em posts",
    "posts_engagement": "Engajamento em posts",
    "posts_avg_engagement_per_post": "Media de engajamento por post",
    "posts_reach": "Alcance dos posts",
    "posts_impressions": "Impressoes dos posts",
    "posts_saved": "Salvamentos dos posts",
    "posts_shares": "Compartilhamentos dos posts",
    "posts_views": "Visualizacoes dos posts",
}

VOICE_PROFILES = {
    "CMO": "Foque em crescimento, posicionamento e risco reputacional. Priorize decisoes trimestrais.",
    "HEAD_GROWTH": "Foque em aquisicao, retencao e experimentos. Impacto em MQL, CAC, LTV e ramp de canais.",
    "PERFORMANCE_MIDIA": "Foque em mix, criativo, frequencia e orcamento. Proximos testes da sprint.",
}

ANALYSIS_TYPE_ALIASES = {
    "descritiva": "descriptive",
    "descricao": "descriptive",
    "descriptive": "descriptive",
    "preditiva": "predictive",
    "predictive": "predictive",
    "prescritiva": "prescriptive",
    "prescriptive": "prescriptive",
    "geral": "general",
    "overall": "general",
    "all": "general",
    "general": "general",
}

FOCUS_ALIASES = {
    "branding": "branding",
    "brand": "branding",
    "negocio": "negocio",
    "business": "negocio",
    "conexao": "conexao",
    "integrada": "conexao",
    "integrated": "conexao",
    "panorama": "panorama",
    "geral": "panorama",
}

TYPE_BLOCKS = {
    "descriptive": "types/descriptive.md",
    "predictive": "types/predictive.md",
    "prescriptive": "types/prescriptive.md",
    "general": "types/general.md",
}

FOCUS_BLOCKS = {
    "branding": "focus/branding.md",
    "negocio": "focus/negocio.md",
    "conexao": "focus/conexao.md",
    "panorama": "focus/panorama.md",
}

OUTPUT_BLOCKS = {
    "detalhado": "blocks/output_detailed.md",
    "resumido": "blocks/output_summary.md",
    "topicos": "blocks/output_topics.md",
}

PLATFORM_BLOCKS = {
    "instagram": "platforms/instagram.md",
    "facebook": "platforms/facebook.md",
    "google_analytics": "platforms/google_analytics.md",
    "linkedin": "platforms/linkedin.md",
    "meta_ads": "platforms/meta_ads.md",
}


def normalize_analysis_type(value: str) -> str:
    return ANALYSIS_TYPE_ALIASES.get((value or "descriptive").strip().lower(), "descriptive")


def normalize_focus(value: str) -> str:
    return FOCUS_ALIASES.get((value or "panorama").strip().lower(), "panorama")


def normalize_output_format(value: str) -> str:
    normalized = (value or "detalhado").strip().lower()
    if normalized in ("topicos", "tópicos"):
        return "topicos"
    if normalized == "resumido":
        return "resumido"
    return "detalhado"


def format_platforms(platforms: Iterable[str]) -> str:
    labels = [PLATFORM_DISPLAY.get(p, p) for p in platforms if p]
    if not labels:
        return "todas as plataformas"
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " e " + labels[-1]


def split_platform_and_base(column: str) -> Tuple[str, str]:
    for platform in sorted(PLATFORM_DISPLAY.keys(), key=len, reverse=True):
        prefix = f"{platform}_"
        if column.startswith(prefix):
            return platform, column[len(prefix):]
    if "_" not in column:
        return "", column
    return column.split("_", 1)


def friendly_metric_label(column: str) -> str:
    platform, base = split_platform_and_base(column)
    platform_label = PLATFORM_DISPLAY.get(platform, platform.title() if platform else "")
    base_label = BASE_LABELS.get(base, base.replace("_", " ").title())
    return f"{base_label} ({platform_label})" if platform_label else base_label


def get_word_cap(analysis_type: str, output_format: str) -> int:
    base_caps: Dict[str, int] = {
        "descriptive": 900,
        "predictive": 900,
        "prescriptive": 1000,
        "general": 1100,
    }
    base_cap = base_caps.get(normalize_analysis_type(analysis_type), 500)
    fmt = normalize_output_format(output_format)
    if fmt == "resumido":
        return int(base_cap * 0.45)
    if fmt == "topicos":
        return int(base_cap * 0.7)
    return int(base_cap * 1.1)


def resolve_type_block(analysis_type: str) -> str:
    return TYPE_BLOCKS[normalize_analysis_type(analysis_type)]


def resolve_focus_block(analysis_focus: str) -> str:
    return FOCUS_BLOCKS[normalize_focus(analysis_focus)]


def resolve_output_block(output_format: str) -> str:
    return OUTPUT_BLOCKS[normalize_output_format(output_format)]


def resolve_platform_blocks(platforms: List[str]) -> List[str]:
    return [
        PLATFORM_BLOCKS[platform]
        for platform in platforms
        if platform in PLATFORM_BLOCKS
    ]
