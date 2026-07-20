import pandas as pd

from utils.dataframe import PlatformDataFrameNormalizer


def test_normalizer_renames_date_and_prefixes_platform_columns():
    df = pd.DataFrame(
        {
            "date": ["2026-07-02", "2026-07-01"],
            "id_customer": [1, 1],
            "reach": [20, 10],
            "views": [200, 100],
        }
    )

    normalized = PlatformDataFrameNormalizer().normalize(df, "instagram")

    assert normalized.columns.tolist() == ["data", "instagram_reach", "instagram_views"]
    assert normalized["data"].dt.strftime("%Y-%m-%d").tolist() == ["2026-07-01", "2026-07-02"]
    assert normalized["instagram_reach"].tolist() == [10, 20]


def test_normalizer_applies_platform_schema_before_prefix():
    df = pd.DataFrame(
        {
            "data": ["2026-07-01"],
            "page_impressions": [100],
            "page_impressions_unique": [40],
            "page_follows": [3],
        }
    )

    normalized = PlatformDataFrameNormalizer().normalize(df, "facebook")

    assert normalized.columns.tolist() == [
        "data",
        "facebook_impressions",
        "facebook_reach",
        "facebook_followers",
    ]


def test_normalizer_merge_outer_joins_by_date():
    normalizer = PlatformDataFrameNormalizer()
    instagram = pd.DataFrame(
        {
            "data": pd.to_datetime(["2026-07-01", "2026-07-02"]),
            "instagram_reach": [10, 20],
        }
    )
    facebook = pd.DataFrame(
        {
            "data": pd.to_datetime(["2026-07-02", "2026-07-03"]),
            "facebook_reach": [30, 40],
        }
    )

    merged = normalizer.merge([instagram, facebook])

    assert merged["data"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-07-01",
        "2026-07-02",
        "2026-07-03",
    ]
    assert merged["instagram_reach"].tolist()[:2] == [10.0, 20.0]
    assert pd.isna(merged["instagram_reach"].iloc[2])
    assert pd.isna(merged["facebook_reach"].iloc[0])
    assert merged["facebook_reach"].tolist()[1:] == [30.0, 40.0]
