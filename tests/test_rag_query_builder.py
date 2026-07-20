from utils.rag import RAGQueryBuilder


def test_rag_query_builder_includes_core_context():
    query = RAGQueryBuilder().build(
        analysis_query="Explique a queda de alcance.",
        platforms=["instagram"],
        summary={
            "meta": {"selected_metrics": ["instagram_reach", "instagram_views"]},
            "anomalies": {"instagram_reach": [{"date": "2026-07-10", "value": 12}]},
        },
        analysis_type="descriptive",
        analysis_focus="branding",
    )

    assert "Explique a queda de alcance." in query
    assert "tipo=descriptive" in query
    assert "foco=branding" in query
    assert "metricas-chave: instagram_reach, instagram_views" in query
    assert "metricas-com-picos: instagram_reach" in query
    assert "plataformas: instagram" in query


def test_rag_query_builder_limits_metric_lists():
    query = RAGQueryBuilder().build(
        analysis_query="",
        platforms=["instagram", "meta_ads"],
        summary={
            "meta": {
                "selected_metrics": [
                    "m1",
                    "m2",
                    "m3",
                    "m4",
                    "m5",
                    "m6",
                    "m7",
                ]
            },
            "anomalies": {
                "a1": [1],
                "a2": [1],
                "a3": [1],
                "a4": [1],
                "a5": [1],
                "a6": [1],
                "a7": [1],
            },
        },
        analysis_type="general",
        analysis_focus="panorama",
    )

    assert "metricas-chave: m1, m2, m3, m4, m5, m6" in query
    assert "m7" not in query
    assert "metricas-com-picos: a1, a2, a3, a4, a5, a6" in query
    assert "a7" not in query


def test_rag_query_builder_preserves_instagram_post_metrics():
    query = RAGQueryBuilder().build(
        analysis_query="Analise conteudos que performaram melhor.",
        platforms=["instagram"],
        summary={
            "meta": {
                "selected_metrics": [
                    "instagram_reach",
                    "instagram_posts_count",
                    "instagram_posts_engagement",
                ]
            },
            "anomalies": {},
        },
        analysis_type="descriptive",
        analysis_focus="panorama",
    )

    assert "instagram_posts_count" in query
    assert "instagram_posts_engagement" in query
