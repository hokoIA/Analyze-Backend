import pandas as pd

from utils.summary import OrganicSummaryBuilder


def _sample_df():
    return pd.DataFrame(
        {
            "data": pd.to_datetime(
                [
                    "2026-07-01",
                    "2026-07-02",
                    "2026-07-03",
                    "2026-07-04",
                ]
            ),
            "instagram_reach": [10, 20, 30, 40],
            "instagram_views": [100, 120, 140, 160],
            "instagram_followers": [300, 301, 302, 304],
            "ignored_text": ["a", "b", "c", "d"],
        }
    )


def test_organic_summary_builder_builds_expected_kpis():
    summary = OrganicSummaryBuilder().build(_sample_df(), ["instagram"])

    assert summary["period"] == {"start": "2026-07-01", "end": "2026-07-04"}
    assert summary["kpis"]["instagram_reach"]["sum"] == 100
    assert summary["kpis"]["instagram_reach"]["mean"] == 25
    assert summary["kpis"]["instagram_views"]["sum"] == 520
    assert summary["meta"]["platforms"] == ["instagram"]
    assert summary["meta"]["selected_metrics"] == [
        "instagram_reach",
        "instagram_views",
        "instagram_followers",
    ]


def test_organic_summary_builder_adds_highlights_and_segments():
    summary = OrganicSummaryBuilder().build(_sample_df(), ["instagram"])

    assert summary["highlights"]["instagram_reach"][0] == {
        "date": "2026-07-04",
        "value": 40.0,
    }
    assert "instagram_reach_by_weekday" in summary["segments"]
    assert "instagram_reach_dod_mean" in summary["trends"]
    assert summary["meta"]["variance_hint"] in {"baixa", "media", "alta"}


def test_organic_summary_builder_falls_back_to_metric_columns():
    df = pd.DataFrame(
        {
            "data": pd.to_datetime(["2026-07-01", "2026-07-02"]),
            "custom_metric": [1, 2],
        }
    )

    summary = OrganicSummaryBuilder().build(df, ["unknown"])

    assert summary["meta"]["selected_metrics"] == ["custom_metric"]
    assert summary["kpis"]["custom_metric"]["sum"] == 3
