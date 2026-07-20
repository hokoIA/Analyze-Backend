from __future__ import annotations

from typing import Dict, List

import pandas as pd


PLATFORM_SCHEMA: Dict[str, Dict[str, str]] = {
    "instagram": {
        "reach": "reach",
        "views": "views",
        "followers": "followers",
    },
    "facebook": {
        "page_impressions": "impressions",
        "page_impressions_unique": "reach",
        "page_follows": "followers",
    },
    "google_analytics": {
        "impressions": "impressions",
        "traffic_direct": "traffic_direct",
        "traffic_organic_search": "traffic_organic_search",
        "traffic_organic_social": "traffic_organic_social",
        "search_volume": "search_volume",
    },
    "linkedin": {
        "impressions": "impressions",
        "followers": "followers",
    },
    "meta_ads": {
        "investment": "investment",
        "impressions": "impressions",
        "reach": "reach",
        "frequency": "frequency",
        "cpm": "cpm",
        "ctr": "ctr",
        "cpc": "cpc",
        "conversationsStarted": "conversations_started",
        "roas": "roas",
        "costPerLead": "cost_per_lead",
    },
}


class PlatformDataFrameNormalizer:
    def normalize_platform_df(self, df: pd.DataFrame, platform: str) -> pd.DataFrame:
        out = df.copy()

        if "data" not in out.columns and "date" in out.columns:
            out = out.rename(columns={"date": "data"})

        drop_candidates = [
            column
            for column in out.columns
            if column.lower() in {"id_customer", "agency_id", "client_id"}
        ]
        if drop_candidates:
            out = out.drop(columns=drop_candidates, errors="ignore")

        schema = PLATFORM_SCHEMA.get(platform, {})
        out = out.rename(columns={orig: canon for orig, canon in schema.items() if orig in out.columns})

        renamed = {}
        for column in out.columns:
            if column == "data":
                continue
            if not column.startswith(f"{platform}_"):
                renamed[column] = f"{platform}_{column}"
        if renamed:
            out = out.rename(columns=renamed)

        return out

    def prepare_dates(self, df: pd.DataFrame, tz: str = "America/Sao_Paulo") -> pd.DataFrame:
        out = df.copy()
        series = pd.to_datetime(out["data"], errors="coerce")

        if getattr(series.dt, "tz", None) is not None:
            series = series.dt.tz_convert(tz).dt.tz_localize(None)

        out["data"] = series.dt.normalize()
        out = out.sort_values("data").reset_index(drop=True)
        return out

    def normalize(self, df: pd.DataFrame, platform: str) -> pd.DataFrame:
        return self.prepare_dates(self.normalize_platform_df(df, platform))

    def merge(self, dfs: List[pd.DataFrame]) -> pd.DataFrame:
        if not dfs:
            return pd.DataFrame({"data": []})
        merged = dfs[0]
        for add in dfs[1:]:
            merged = pd.merge(merged, add, on="data", how="outer")
        return merged.sort_values("data").reset_index(drop=True)
