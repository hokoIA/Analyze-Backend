from utils.external_data import ExternalDataSummaryBuilder
from utils.prompts.system_prompts import build_narrative_prompt


def _external_data():
    return {
        "source": "api_gateway",
        "source_mode": "api_gateway_direct",
        "instagram_posts": {
            "period": {"startDate": "2026-07-01", "endDate": "2026-07-15"},
            "resource": {"id": "1789", "username": "@cliente"},
            "posts": [
                {
                    "id": "post_1",
                    "timestamp": "2026-07-05T12:00:00Z",
                    "media_type": "IMAGE",
                    "caption": "Post institucional com foco em autoridade.",
                    "permalink": "https://instagram.com/p/post_1",
                    "like_count": 10,
                    "comments_count": 3,
                    "insights": {"reach": 120, "impressions": 180, "saved": 2},
                },
                {
                    "id": "post_2",
                    "timestamp": "2026-07-10T12:00:00Z",
                    "media_type": "REELS",
                    "caption": "Video educativo.",
                    "permalink": "https://instagram.com/p/post_2",
                    "like_count": 20,
                    "comments_count": 5,
                    "insights": {"reach": 300, "impressions": 430, "shares": 4, "views": 520},
                },
            ],
        },
    }


def test_build_instagram_posts_external_summary_adds_post_metrics():
    summary = ExternalDataSummaryBuilder().build_instagram_posts_summary(
        external_data=_external_data(),
        platforms=["instagram"],
        start_date="2026-07-01",
        end_date="2026-07-15",
    )

    assert summary is not None
    assert summary["period"] == {"start": "2026-07-01", "end": "2026-07-15"}
    assert summary["kpis"]["instagram_posts_count"]["sum"] == 2
    assert summary["kpis"]["instagram_posts_likes"]["sum"] == 30
    assert summary["kpis"]["instagram_posts_comments"]["sum"] == 8
    assert summary["kpis"]["instagram_posts_engagement"]["sum"] == 44
    assert summary["kpis"]["instagram_posts_avg_engagement_per_post"]["mean"] == 22
    assert summary["owned_media"]["row_counts"]["posts"] == 2
    assert summary["highlights"]["instagram_posts_by_engagement"][0]["id"] == "post_2"


def test_combine_summaries_preserves_organic_metrics_and_adds_posts():
    builder = ExternalDataSummaryBuilder()
    db_summary = {
        "period": {"start": "2026-07-01", "end": "2026-07-15"},
        "kpis": {"instagram_reach": {"sum": 1000}},
        "anomalies": {},
        "trends": {},
        "segments": {},
        "highlights": {"instagram_reach": [{"date": "2026-07-10", "value": 300}]},
        "meta": {
            "platforms": ["instagram"],
            "columns": ["instagram_reach"],
            "selected_metrics": ["instagram_reach"],
        },
    }
    posts_summary = builder.build_instagram_posts_summary(
        external_data=_external_data(),
        platforms=["instagram"],
        start_date="2026-07-01",
        end_date="2026-07-15",
    )

    combined = builder.combine_summaries(db_summary, posts_summary, ["instagram"])

    assert combined["kpis"]["instagram_reach"]["sum"] == 1000
    assert combined["kpis"]["instagram_posts_count"]["sum"] == 2
    assert "instagram_reach" in combined["meta"]["selected_metrics"]
    assert "instagram_posts_engagement" in combined["meta"]["selected_metrics"]
    assert combined["owned_media"]["posts"]["totals"]["engagement"] == 44


def test_prompt_contains_instagram_post_evidence_in_data_block():
    posts_summary = ExternalDataSummaryBuilder().build_instagram_posts_summary(
        external_data=_external_data(),
        platforms=["instagram"],
        start_date="2026-07-01",
        end_date="2026-07-15",
    )

    prompt = build_narrative_prompt(
        platforms=["instagram"],
        analysis_type="descriptive",
        analysis_focus="panorama",
        analysis_query="Analise o periodo.",
        context_text="Cliente de teste.",
        summary_json=posts_summary,
        output_format="detalhado",
        bilingual=True,
    )

    assert "[DADOS (JSON CONFIAVEL)]" in prompt
    assert "instagram_posts_engagement -> Engajamento em posts (Instagram)" in prompt
    assert "instagram_posts_by_engagement" in prompt
    assert "Post institucional com foco em autoridade." in prompt
