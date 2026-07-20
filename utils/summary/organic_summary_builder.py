from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


PREFERRED_BASES = (
    "reach",
    "views",
    "impressions",
    "followers",
    "traffic_direct",
    "traffic_organic_search",
    "traffic_organic_social",
    "search_volume",
    "investment",
    "frequency",
    "cpm",
    "ctr",
    "cpc",
    "conversations_started",
    "roas",
    "cost_per_lead",
)


def basic_kpis(df: pd.DataFrame, cols: List[str]) -> Dict[str, Dict[str, float]]:
    kpis: Dict[str, Dict[str, float]] = {}
    for column in cols:
        if column in df.columns:
            series = df[column].fillna(0)
            kpis[column] = {
                "mean": float(series.mean()),
                "median": float(series.median()),
                "p95": float(series.quantile(0.95)),
                "sum": float(series.sum()),
                "non_zero_days": float((series > 0).sum()),
                "days": float(series.shape[0]),
            }
    return kpis


def mad_anomalies(df: pd.DataFrame, col: str, zcut: float = 3.0) -> List[Dict[str, Any]]:
    if col not in df.columns:
        return []

    series = pd.to_numeric(df[col], errors="coerce")
    valid_mask = series.notna()
    if valid_mask.sum() == 0:
        return []

    valid_series = series.loc[valid_mask]
    median = valid_series.median()
    mad = (valid_series - median).abs().median()
    if mad == 0 or pd.isna(mad):
        return []

    z_score = 0.6745 * (valid_series - median) / mad
    outlier_idx = z_score.loc[z_score.abs() >= zcut].index
    outliers = df.loc[outlier_idx, ["data", col]].copy()
    outliers[col] = pd.to_numeric(outliers[col], errors="coerce")
    outliers = outliers.dropna(subset=["data", col])

    records: List[Dict[str, Any]] = []
    for _, row in outliers.iterrows():
        records.append({"data": str(row["data"].date()), col: float(row[col])})
    return records


def dod_change_mean(df: pd.DataFrame, col: str) -> Optional[float]:
    if col not in df.columns:
        return None
    series = df[col].fillna(0)
    pct = series.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    return float(pct.mean()) if not pct.empty else None


def weekday_breakdown(df: pd.DataFrame, col: str) -> List[Dict[str, Any]]:
    if col not in df.columns or "data" not in df.columns:
        return []
    tmp = df.copy()
    try:
        tmp["weekday"] = tmp["data"].dt.day_name(locale="pt_BR")
    except Exception:
        weekday_map = {
            0: "Monday",
            1: "Tuesday",
            2: "Wednesday",
            3: "Thursday",
            4: "Friday",
            5: "Saturday",
            6: "Sunday",
        }
        tmp["weekday"] = tmp["data"].dt.day_of_week.map(weekday_map)
    grouped = tmp.groupby("weekday")[col].agg(["mean", "sum", "median"]).reset_index()
    records: List[Dict[str, Any]] = []
    for _, row in grouped.iterrows():
        records.append(
            {
                "weekday": str(row["weekday"]),
                "mean": float(row["mean"]),
                "sum": float(row["sum"]),
                "median": float(row["median"]),
            }
        )
    return records


class OrganicSummaryBuilder:
    def build(self, merged_df: pd.DataFrame, platforms: List[str]) -> Dict[str, Any]:
        summary = self.compute(merged_df, platforms)
        return self.enrich(merged_df, platforms, summary)

    def compute(self, merged_df: pd.DataFrame, platforms: List[str]) -> Dict[str, Any]:
        all_cols = merged_df.columns.tolist()
        metric_cols = [column for column in all_cols if column != "data"]

        candidates: List[str] = []
        for base in PREFERRED_BASES:
            for platform in platforms:
                platform_column = f"{platform}_{base}"
                if platform_column in merged_df.columns:
                    candidates.append(platform_column)

        if not candidates:
            candidates = metric_cols

        summary: Dict[str, Any] = {
            "period": {
                "start": str(merged_df["data"].min().date()) if not merged_df.empty else None,
                "end": str(merged_df["data"].max().date()) if not merged_df.empty else None,
            },
            "kpis": basic_kpis(merged_df, candidates),
            "anomalies": {column: mad_anomalies(merged_df, column) for column in candidates},
            "trends": {f"{column}_dod_mean": dod_change_mean(merged_df, column) for column in candidates},
            "segments": {f"{column}_by_weekday": weekday_breakdown(merged_df, column) for column in candidates},
            "meta": {"platforms": platforms, "columns": all_cols, "selected_metrics": candidates},
        }

        highlights = {}
        for column in candidates:
            df_column = merged_df[["data", column]].dropna()
            if df_column.empty:
                continue
            top3 = df_column.sort_values(column, ascending=False).head(3)
            highlights[column] = [
                {"date": str(row["data"].date()), "value": float(row[column])}
                for _, row in top3.iterrows()
            ]
        summary["highlights"] = highlights

        try:
            period = summary["period"]
            if period["start"] and period["end"]:
                start = pd.to_datetime(period["start"])
                end = pd.to_datetime(period["end"])
                delta = (end - start) or pd.Timedelta(days=1)
                prev_start, prev_end = start - delta, start
                prev_mask = (merged_df["data"] >= prev_start) & (merged_df["data"] < prev_end)
                cur_mask = (merged_df["data"] >= start) & (merged_df["data"] <= end)
                comparison = {}
                for column in candidates:
                    cur = merged_df.loc[cur_mask, column].mean()
                    prev = merged_df.loc[prev_mask, column].mean()
                    if pd.notna(cur) and pd.notna(prev) and prev != 0:
                        comparison[column] = {
                            "cur": float(cur),
                            "prev": float(prev),
                            "delta_pct": float((cur / prev) - 1),
                        }
                summary["period_compare"] = comparison
        except Exception:
            pass

        try:
            variances = []
            for column in candidates:
                series = merged_df[column].dropna()
                if len(series) > 3:
                    variances.append(float(np.var(series)))
            variance_hint = "baixa"
            if variances:
                q3 = np.quantile(variances, 0.75)
                q1 = np.quantile(variances, 0.25)
                variance_hint = "alta" if q3 > 0 and (q3 - q1) > 0 else "media"
            summary["meta"]["variance_hint"] = variance_hint
        except Exception:
            summary["meta"]["variance_hint"] = "media"

        return summary

    def enrich(self, merged_df: pd.DataFrame, platforms: List[str], summary: Dict[str, Any]) -> Dict[str, Any]:
        if "data" in merged_df.columns:
            merged_df = merged_df.copy()
            merged_df["data"] = pd.to_datetime(merged_df["data"], errors="coerce")
            merged_df = merged_df.dropna(subset=["data"]).sort_values("data")

        metric_cols = []
        for column in merged_df.columns:
            if column == "data":
                continue
            try:
                if np.issubdtype(merged_df[column].dtype, np.number):
                    metric_cols.append(column)
            except Exception:
                pass

        highlights = {}
        for column in metric_cols:
            df_column = merged_df[["data", column]].dropna()
            if df_column.empty:
                continue
            top3 = df_column.sort_values(column, ascending=False).head(3)
            highlights[column] = [
                {"date": date.strftime("%Y-%m-%d"), "value": float(value)}
                for date, value in zip(top3["data"], top3[column])
            ]
        summary["highlights"] = highlights

        try:
            variances = []
            for column in metric_cols:
                values = merged_df[column].dropna().values
                if values.size > 3:
                    variances.append(float(np.var(values)))
            variance_hint = "media"
            if variances:
                q1, q3 = np.percentile(variances, [25, 75])
                variance_hint = "alta" if (q3 - q1) > 0 else "baixa"
            summary.setdefault("meta", {})["variance_hint"] = variance_hint
        except Exception:
            summary.setdefault("meta", {})["variance_hint"] = "media"

        return summary
