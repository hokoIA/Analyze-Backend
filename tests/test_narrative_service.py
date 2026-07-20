from types import SimpleNamespace

from utils.llm.config import get_llm_config
from utils.narrative import AnalysisNarrativeService


class FakeLLM:
    calls = []
    responses = []
    kwargs = {}

    def __init__(self, **kwargs):
        FakeLLM.kwargs = kwargs

    def invoke(self, messages):
        FakeLLM.calls.append(messages)
        if FakeLLM.responses:
            return SimpleNamespace(content=FakeLLM.responses.pop(0))
        return SimpleNamespace(content="")


def _reset_fake_llm(*responses):
    FakeLLM.calls = []
    FakeLLM.responses = list(responses)
    FakeLLM.kwargs = {}


def _service(chat_model_cls=FakeLLM):
    return AnalysisNarrativeService(
        llm_config=get_llm_config({}),
        openai_api_key="test-key",
        chat_model_cls=chat_model_cls,
    )


def test_narrative_service_generates_prompt_and_skips_refine_when_specific():
    _reset_fake_llm("No dia 2026-07-10, o alcance chegou a 1200.")

    result = _service().generate(
        platforms=["instagram"],
        analysis_type="descriptive",
        analysis_query="Analise o periodo.",
        context_text="Historico do cliente.",
        summary={
            "period": {"start": "2026-07-01", "end": "2026-07-15"},
            "meta": {"selected_metrics": ["instagram_reach"]},
            "kpis": {"instagram_reach": {"sum": 1200}},
        },
        client_name="Cliente Teste",
    )

    assert result == "No dia 2026-07-10, o alcance chegou a 1200."
    assert FakeLLM.kwargs["model"] == "gpt-5.4"
    assert FakeLLM.kwargs["api_key"] == "test-key"
    assert len(FakeLLM.calls) == 1
    assert FakeLLM.calls[0][0]["role"] == "system"
    assert "Cliente Teste" in FakeLLM.calls[0][0]["content"]
    assert "[DADOS (JSON CONFIAVEL)]" in FakeLLM.calls[0][1]["content"]


def test_narrative_service_refines_generic_output():
    _reset_fake_llm("O periodo teve bom desempenho.", "Em 2026-07-10, alcance somou 1200.")

    result = _service().generate(
        platforms=["instagram"],
        analysis_type="descriptive",
        analysis_query="Analise o periodo.",
        context_text="",
        summary={
            "period": {"start": "2026-07-01", "end": "2026-07-15"},
            "meta": {"selected_metrics": ["instagram_reach"]},
            "kpis": {"instagram_reach": {"sum": 1200}},
        },
    )

    assert result == "Em 2026-07-10, alcance somou 1200."
    assert len(FakeLLM.calls) == 2
    assert "editor sênior" in FakeLLM.calls[1][0]["content"]


def test_narrative_service_fallback_when_llm_unavailable():
    result = _service(chat_model_cls=None).generate(
        platforms=["instagram"],
        analysis_type="descriptive",
        analysis_query="Analise o periodo.",
        context_text="",
        summary={"kpis": {"instagram_reach": {"sum": 1200}}},
    )

    assert "ChatOpenAI indisponível" in result
    assert "Resumo JSON:" in result
    assert "Analise o periodo." in result


def test_narrative_service_postprocess_topics_without_bullets():
    result = _service().postprocess_output(
        "Primeiro achado. Segundo achado. Terceiro achado.",
        "topicos",
    )

    assert result.splitlines() == [
        "- Primeiro achado.",
        "- Segundo achado.",
        "- Terceiro achado.",
    ]


def test_narrative_service_postprocess_summary_limits_sentences():
    result = _service().postprocess_output(
        "Um. Dois. Tres. Quatro. Cinco. Seis. Sete.",
        "resumido",
    )

    assert result == "Um. Dois. Tres. Quatro. Cinco."
