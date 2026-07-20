from utils.prompts.analysis import (
    get_business_analysis_query,
    get_default_analysis_query,
    render_refine_prompt,
)
from utils.prompts.system_prompts import (
    get_business_analysis_query as legacy_business_query,
)


def test_default_analysis_query_uses_platform_and_period():
    query = get_default_analysis_query(
        "descriptive",
        ["instagram"],
        " no periodo de 2026-06-01 a 2026-06-30",
    )

    assert "Instagram" in query
    assert "2026-06-01" in query
    assert "descritiva" in query.lower()


def test_business_analysis_query_is_loaded_from_markdown():
    query = get_business_analysis_query()

    assert "analise de negocio completa" in query.lower()
    assert query == legacy_business_query()


def test_render_refine_prompt_includes_text_and_summary():
    prompt = render_refine_prompt(
        "Texto muito generico.",
        {"kpis": {"instagram_reach": {"sum": 1200}}},
    )

    assert "[TEXTO]" in prompt
    assert "Texto muito generico." in prompt
    assert "[DADOS PARA CONSULTA INTERNA]" in prompt
    assert "Nao mencione JSON, API, RAG, prompt, modelo, banco de dados, payload ou nomes internos de campos." in prompt
    assert "instagram_reach" in prompt
    assert "1200" in prompt
