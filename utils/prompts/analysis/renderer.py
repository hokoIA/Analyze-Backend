from __future__ import annotations

import json
from typing import Any, Dict, List

from .contracts import AnalysisPromptInput
from .loader import load_prompt_block, render_prompt_block
from .registry import (
    PLATFORM_DISPLAY,
    VOICE_PROFILES,
    format_platforms,
    friendly_metric_label,
    get_word_cap,
    normalize_analysis_type,
    normalize_focus,
    normalize_output_format,
    resolve_focus_block,
    resolve_output_block,
    resolve_platform_blocks,
    resolve_type_block,
)


DEFAULT_QUERY_BLOCKS = {
    "descriptive": "defaults/query_descriptive.md",
    "predictive": "defaults/query_predictive.md",
    "prescriptive": "defaults/query_prescriptive.md",
    "general": "defaults/query_general.md",
}


def build_vocabulary_block(summary_json: Dict[str, Any]) -> str:
    selected = list((summary_json or {}).get("meta", {}).get("selected_metrics", [])) or []
    if not selected:
        return "[VOCABULARIO]\n(Nao ha metricas selecionadas; use rotulos amigaveis.)"
    lines = [f"- {column} -> {friendly_metric_label(column)}" for column in selected]
    return "[VOCABULARIO]\nNunca exiba nomes internos; traduza assim:\n" + "\n".join(lines)


def build_platform_prompt(platforms: List[str]) -> str:
    blocks = []
    for block_path in resolve_platform_blocks(platforms):
        blocks.append(load_prompt_block(block_path))

    header = "[PLATAFORMAS]\n" + format_platforms(platforms)
    return header + ("\n" + "\n".join(blocks) if blocks else "")


def build_decision_brief_block(analysis_type: str, decision_mode: str) -> str:
    if decision_mode != "decision_brief":
        return ""
    atype = normalize_analysis_type(analysis_type)
    if atype == "descriptive":
        return load_prompt_block("blocks/decision_brief_descriptive.md")
    return load_prompt_block("blocks/decision_brief_actionable.md")


def build_bilingual_block(enabled: bool) -> str:
    if enabled:
        return load_prompt_block("blocks/bilingual.md")
    return "Responda diretamente em portugues do Brasil."


def build_rules_block(input_data: AnalysisPromptInput, word_cap: int) -> str:
    atype = normalize_analysis_type(input_data.analysis_type)
    fmt = normalize_output_format(input_data.output_format)
    rules = [
        "- Conecte achados a impacto: receita, crescimento, eficiencia, risco ou oportunidade.",
        "- Nao invente numeros; use somente o JSON e o contexto recuperado.",
        "- Para cada insight central, use a sequencia: evidencia observada -> interpretacao -> implicacao.",
        "- Se uma leitura depender de inferencia, use linguagem proporcional: indica, sugere, pode sinalizar.",
        "- Remova da resposta final qualquer termo tecnico interno que nao faca sentido para o cliente final.",
    ]

    if fmt == "detalhado":
        rules.append(
            "- Em formato detalhado, cubra a trajetoria do periodo: inicio, meio e fim."
        )

    if atype == "descriptive":
        rules.insert(
            0,
            "- Reconstrua a trajetoria do periodo, nao apenas 2 ou 3 dias de pico."
        )
    elif atype == "predictive":
        rules.insert(
            1,
            "- Use tendencias numericas do JSON para calibrar cenarios e ordens de grandeza."
        )
    elif atype == "prescriptive":
        rules.insert(
            1,
            "- Baseie cada recomendacao em problemas ou oportunidades visiveis nos dados."
        )

    rules.append(f"- Limite de {word_cap} palavras, com tolerancia de 10%.")
    return "[REGRAS COMPLEMENTARES]\n" + "\n".join(rules)


def render_analysis_prompt(input_data: AnalysisPromptInput) -> str:
    atype = normalize_analysis_type(input_data.analysis_type)
    focus = normalize_focus(input_data.analysis_focus)
    fmt = normalize_output_format(input_data.output_format)
    word_cap = get_word_cap(atype, fmt)

    variables = {
        "voice_profile": input_data.voice_profile,
        "voice_profile_instruction": VOICE_PROFILES.get(input_data.voice_profile, ""),
        "analysis_focus": focus,
        "narrative_style": input_data.narrative_style,
        "word_cap": word_cap,
    }

    sections = [
        load_prompt_block("blocks/base.md"),
        load_prompt_block("blocks/style.md"),
        render_prompt_block("blocks/persona.md", variables),
        load_prompt_block(resolve_focus_block(focus)),
        build_platform_prompt(input_data.platforms),
        build_vocabulary_block(input_data.summary_json),
        load_prompt_block("blocks/evidence.md"),
        render_prompt_block("blocks/narrative_style.md", variables),
        "[TAREFA]\n" + load_prompt_block(resolve_type_block(atype)),
        build_rules_block(input_data, word_cap),
        "[CONTEXTO (RAG)]\n" + (input_data.context_text or "(sem contexto recuperado)"),
        "[DADOS (JSON CONFIAVEL)]\n" + json.dumps(input_data.summary_json, ensure_ascii=False),
        build_decision_brief_block(atype, input_data.decision_mode),
        load_prompt_block("blocks/final_quality.md"),
        load_prompt_block(resolve_output_block(fmt)),
        "[PEDIDO DO USUARIO]\n" + (input_data.analysis_query or ""),
        build_bilingual_block(input_data.bilingual),
    ]

    return "\n\n".join(section for section in sections if section).strip()


def get_default_analysis_query(
    analysis_type: str,
    platforms: List[str],
    date_filter: str = "",
) -> str:
    atype = normalize_analysis_type(analysis_type)
    return render_prompt_block(
        DEFAULT_QUERY_BLOCKS.get(atype, DEFAULT_QUERY_BLOCKS["general"]),
        {
            "platforms": format_platforms(platforms),
            "date_filter": date_filter or "",
        },
    )


def get_business_analysis_query() -> str:
    return load_prompt_block("defaults/query_business_general.md")


def render_refine_prompt(text: str, summary_json: Dict[str, Any]) -> str:
    return render_prompt_block(
        "blocks/refine_generic.md",
        {
            "text": text or "",
            "summary_json": json.dumps(summary_json or {}, ensure_ascii=False),
        },
    )
