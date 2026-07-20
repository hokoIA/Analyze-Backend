from utils.prompts.analysis import AnalysisPromptInput, render_analysis_prompt


EXPECTED_SECTION_ORDER = [
    "[ROLE]",
    "[GUIA DE ESTILO]",
    "[PERFIL]",
    "[ENVIESAMENTO: Panorama Integrado]",
    "[PLATAFORMAS]",
    "[VOCABULARIO]",
    "[CRITERIOS DE EVIDENCIA]",
    "[ESTILO NARRATIVO]",
    "[TAREFA]",
    "[REGRAS COMPLEMENTARES]",
    "[CONTEXTO (RAG)]",
    "[DADOS (JSON CONFIAVEL)]",
    "[DECISION BRIEF]",
    "[QUALIDADE FINAL]",
    "[SAIDA]",
    "[PEDIDO DO USUARIO]",
]


def _render_prompt(**overrides):
    payload = {
        "platforms": ["instagram"],
        "analysis_type": "descriptive",
        "analysis_focus": "panorama",
        "analysis_query": "Analise o periodo selecionado.",
        "context_text": "Cliente usa conteudo educativo para gerar autoridade.",
        "summary_json": {
            "period": {"start": "2026-07-01", "end": "2026-07-15"},
            "meta": {"selected_metrics": ["instagram_reach", "instagram_views"]},
            "kpis": {
                "instagram_reach": {"sum": 1200},
                "instagram_views": {"sum": 1800},
            },
        },
        "output_format": "detalhado",
        "bilingual": True,
        "voice_profile": "CMO",
        "decision_mode": "decision_brief",
        "narrative_style": "SCQA",
    }
    payload.update(overrides)
    return render_analysis_prompt(AnalysisPromptInput(**payload))


def _assert_ordered_sections(prompt: str):
    cursor = -1
    for section in EXPECTED_SECTION_ORDER:
        next_pos = prompt.find(section)
        assert next_pos > cursor, f"section missing or out of order: {section}"
        cursor = next_pos


def test_descriptive_instagram_prompt_snapshot():
    prompt = _render_prompt()

    _assert_ordered_sections(prompt)
    assert "Instagram" in prompt
    assert "instagram_reach -> Alcance (Instagram)" in prompt
    assert "instagram_views -> Visualizacoes (Instagram)" in prompt
    assert '"instagram_reach": {"sum": 1200}' in prompt


def test_general_meta_ads_prompt_snapshot():
    prompt = _render_prompt(
        platforms=["instagram", "meta_ads"],
        analysis_type="general",
        analysis_query="Cruze o comportamento organico com a midia paga.",
        summary_json={
            "period": {"start": "2026-07-01", "end": "2026-07-15"},
            "meta": {
                "selected_metrics": [
                    "instagram_reach",
                    "meta_ads_investment",
                    "meta_ads_impressions",
                    "meta_ads_roas",
                ]
            },
            "kpis": {
                "instagram_reach": {"sum": 1200},
                "meta_ads_investment": {"sum": 900.0},
                "meta_ads_impressions": {"sum": 24000},
                "meta_ads_roas": {"sum": 2.4},
            },
            "paid_media": {
                "platform": "meta_ads",
                "row_counts": {"campaign": 2, "adSet": 4, "ad": 6},
            },
        },
    )

    _assert_ordered_sections(prompt)
    assert "Instagram e Meta Ads" in prompt
    assert "meta_ads_investment -> Investimento (Meta Ads)" in prompt
    assert "meta_ads_roas -> ROAS (Meta Ads)" in prompt
    assert '"paid_media": {"platform": "meta_ads"' in prompt


def test_instagram_posts_prompt_snapshot():
    prompt = _render_prompt(
        summary_json={
            "period": {"start": "2026-07-01", "end": "2026-07-15"},
            "meta": {
                "selected_metrics": [
                    "instagram_reach",
                    "instagram_posts_count",
                    "instagram_posts_engagement",
                    "instagram_posts_avg_engagement_per_post",
                ]
            },
            "kpis": {
                "instagram_reach": {"sum": 1200},
                "instagram_posts_count": {"sum": 3},
                "instagram_posts_engagement": {"sum": 90},
                "instagram_posts_avg_engagement_per_post": {"mean": 30},
            },
            "highlights": {
                "instagram_posts_by_engagement": [
                    {
                        "id": "post_1",
                        "created_time": "2026-07-10T12:00:00Z",
                        "caption": "Conteudo educativo sobre vendas.",
                        "likes": 40,
                        "comments": 8,
                        "engagement": 48,
                    }
                ]
            },
            "owned_media": {
                "platform": "instagram",
                "row_counts": {"posts": 3},
                "posts": {
                    "rows": 3,
                    "totals": {"likes": 70, "comments": 20, "engagement": 90},
                    "averages": {"engagement": 30},
                },
            },
        },
    )

    _assert_ordered_sections(prompt)
    assert "instagram_posts_count -> Total de posts (Instagram)" in prompt
    assert "instagram_posts_engagement -> Engajamento em posts (Instagram)" in prompt
    assert "instagram_posts_avg_engagement_per_post -> Media de engajamento por post (Instagram)" in prompt
    assert "instagram_posts_by_engagement" in prompt
    assert "Conteudo educativo sobre vendas." in prompt


def test_prompt_required_blocks_snapshot():
    prompt = _render_prompt()

    for required in [
        "[DADOS (JSON CONFIAVEL)]",
        "[CONTEXTO (RAG)]",
        "[PEDIDO DO USUARIO]",
        "Nao invente numeros",
        "evidencia observada -> interpretacao -> implicacao",
        "Nunca mencione termos tecnicos internos",
        "API, JSON, RAG, prompt, modelo, token, banco de dados, payload, schema ou variavel",
        "entregue apenas em portugues do Brasil",
    ]:
        assert required in prompt
