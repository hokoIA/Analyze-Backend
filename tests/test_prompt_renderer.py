import pytest

from utils.prompts.analysis import AnalysisPromptInput, render_analysis_prompt
from utils.prompts.analysis.loader import load_prompt_block, render_prompt_block
from utils.prompts.system_prompts import (
    build_chat_system_prompt,
    build_narrative_prompt,
    get_analysis_prompt,
    get_platform_prompt,
)


def _sample_prompt_input(**overrides):
    base = {
        "platforms": ["instagram", "meta_ads"],
        "analysis_type": "descriptive",
        "analysis_focus": "panorama",
        "analysis_query": "Explique o desempenho do periodo.",
        "context_text": "Cliente tem foco em autoridade e captacao.",
        "summary_json": {
            "period": {"start": "2026-06-01", "end": "2026-06-30"},
            "meta": {
                "selected_metrics": [
                    "instagram_reach",
                    "meta_ads_investment",
                ]
            },
            "kpis": {
                "instagram_reach": {"sum": 1200},
                "meta_ads_investment": {"sum": 450.0},
            },
        },
        "output_format": "detalhado",
        "granularity": "detalhada",
        "bilingual": True,
        "voice_profile": "CMO",
        "decision_mode": "decision_brief",
        "narrative_style": "SCQA",
    }
    base.update(overrides)
    return AnalysisPromptInput(**base)


def test_load_prompt_block_reads_markdown():
    block = load_prompt_block("blocks/base.md")

    assert "[ROLE]" in block
    assert "ho.ko AI.nalytics" in block


def test_render_prompt_block_keeps_unknown_variables_safe():
    rendered = render_prompt_block("blocks/persona.md", {"voice_profile": "CMO"})

    assert "CMO" in rendered
    assert "{voice_profile_instruction}" in rendered


def test_load_prompt_block_blocks_path_traversal():
    with pytest.raises(ValueError):
        load_prompt_block("../system_prompts.py")


def test_render_analysis_prompt_contains_required_sections():
    prompt = render_analysis_prompt(_sample_prompt_input())

    assert "[DADOS (JSON CONFIAVEL)]" in prompt
    assert "[CONTEXTO (RAG)]" in prompt
    assert "[PEDIDO DO USUARIO]" in prompt
    assert "[ANALISE DESCRITIVA]" in prompt
    assert "[ENVIESAMENTO: Panorama Integrado]" in prompt
    assert "Explique o desempenho do periodo." in prompt


def test_render_analysis_prompt_uses_platforms_and_friendly_metrics():
    prompt = render_analysis_prompt(_sample_prompt_input())

    assert "Instagram e Meta Ads" in prompt
    assert "instagram_reach -> Alcance (Instagram)" in prompt
    assert "meta_ads_investment -> Investimento (Meta Ads)" in prompt


def test_render_analysis_prompt_respects_output_format():
    prompt = render_analysis_prompt(_sample_prompt_input(output_format="resumido"))

    assert "resumo executivo" in prompt.lower()
    assert "Limite de 405 palavras" in prompt


def test_public_build_narrative_prompt_delegates_to_modular_renderer():
    prompt = build_narrative_prompt(
        platforms=["instagram"],
        analysis_type="descriptive",
        analysis_focus="branding",
        analysis_query="Leia o periodo com foco em marca.",
        context_text="Marca tem foco em autoridade.",
        summary_json={
            "meta": {"selected_metrics": ["instagram_reach"]},
            "kpis": {"instagram_reach": {"sum": 500}},
        },
        output_format="detalhado",
        bilingual=True,
    )

    assert "[DADOS (JSON CONFIAVEL)]" in prompt
    assert "[CONTEXTO (RAG)]" in prompt
    assert "[PEDIDO DO USUARIO]" in prompt
    assert "[ENVIESAMENTO: Branding & Comunicacao]" in prompt
    assert "Leia o periodo com foco em marca." in prompt


def test_legacy_prompt_helpers_remain_available():
    assert "Instagram" in get_platform_prompt(["instagram"])
    default_query = get_analysis_prompt("descriptive", ["instagram"]).lower()
    assert "descritiva" in default_query
    assert "instagram" in default_query
    assert "portugu" in build_chat_system_prompt("Cliente").lower()
