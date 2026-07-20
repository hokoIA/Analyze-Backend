from types import SimpleNamespace

import pandas as pd

from utils.advanced_data_analyst import AdvancedDataAnalyst
from utils.llm.config import get_llm_config
from utils.narrative import AnalysisNarrativeService


class FakeRelationalDB:
    def get_client_data(self, client_id, platform, start_date, end_date):
        assert client_id == "189"
        assert platform == "instagram"
        assert start_date == "2026-07-01"
        assert end_date == "2026-07-15"
        return pd.DataFrame(
            {
                "data": ["2026-07-01", "2026-07-10", "2026-07-15"],
                "reach": [100, 300, 200],
                "views": [150, 420, 260],
                "followers": [1000, 1005, 1010],
            }
        )


class FakeVectorDB:
    last_query = None

    def retrieve_context_for_analysis(self, query, scope, agency_id, client_id, k_total):
        FakeVectorDB.last_query = query
        assert scope == "client"
        assert agency_id == "1"
        assert client_id == "189"
        assert k_total == 8
        return "Contexto historico recuperado."


class FakeLLM:
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def invoke(self, messages):
        FakeLLM.calls.append(messages)
        return SimpleNamespace(content="Em 2026-07-10, o alcance chegou a 300 e os posts somaram engajamento.")


def test_run_analysis_integrates_db_external_posts_rag_and_llm():
    FakeLLM.calls = []
    FakeVectorDB.last_query = None
    analyst = AdvancedDataAnalyst(
        vector_db=FakeVectorDB(),
        relational_db=FakeRelationalDB(),
        openai_api_key="test-key",
        pinecone_api_key="test-pinecone",
    )
    analyst.narrative_service = AnalysisNarrativeService(
        llm_config=get_llm_config({}),
        openai_api_key="test-key",
        chat_model_cls=FakeLLM,
    )

    result = analyst.run_analysis(
        {
            "agency_id": "1",
            "client_id": "189",
            "platforms": ["instagram"],
            "analysis_focus": "panorama",
            "analysis_type": "descriptive",
            "start_date": "2026-07-01",
            "end_date": "2026-07-15",
            "analysis_query": "Analise Instagram e posts do periodo.",
            "output_format": "detalhado",
            "external_data": {
                "source": "api_gateway",
                "source_mode": "api_gateway_direct",
                "instagram_posts": {
                    "period": {"startDate": "2026-07-01", "endDate": "2026-07-15"},
                    "posts": [
                        {
                            "id": "post_1",
                            "timestamp": "2026-07-10T12:00:00Z",
                            "media_type": "IMAGE",
                            "caption": "Conteudo educativo.",
                            "like_count": 20,
                            "comments_count": 5,
                            "insights": {"reach": 180, "impressions": 250, "saved": 2},
                        }
                    ],
                },
            },
        }
    )

    assert result["status"] == "success"
    assert result["error"] is None
    assert result["result"] == "Em 2026-07-10, o alcance chegou a 300 e os posts somaram engajamento."
    assert result["summary"]["kpis"]["instagram_reach"]["sum"] == 600
    assert result["summary"]["kpis"]["instagram_posts_count"]["sum"] == 1
    assert result["summary"]["kpis"]["instagram_posts_engagement"]["sum"] == 27
    assert result["summary"]["owned_media"]["row_counts"]["posts"] == 1
    assert "instagram_posts_count" in FakeVectorDB.last_query
    assert len(FakeLLM.calls) == 1
    assert "[DADOS (JSON CONFIAVEL)]" in FakeLLM.calls[0][1]["content"]
