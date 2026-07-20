from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple


class ExternalDataSummaryBuilder:
    def as_number(self, value: Any) -> float:
        try:
            if value is None or value == "":
                return 0.0
            number = float(value)
            return number if math.isfinite(number) else 0.0
        except Exception:
            return 0.0

    def first_present(self, source: Dict[str, Any], keys: List[str]) -> Any:
        for key in keys:
            if key in source and source.get(key) not in (None, ""):
                return source.get(key)
        return None

    def build(
        self,
        external_data: Optional[Dict[str, Any]],
        platforms: List[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        external_summary = None
        external_platforms: List[str] = []
        if not isinstance(external_data, dict):
            return None, external_platforms

        external_summaries: List[Dict[str, Any]] = []

        if "meta_ads" in platforms:
            meta_ads_summary = self.build_meta_ads_summary(
                external_data=external_data,
                platforms=platforms,
                start_date=start_date,
                end_date=end_date,
            )
            if meta_ads_summary:
                external_summaries.append(meta_ads_summary)
                external_platforms.append("meta_ads")

        if "instagram" in platforms:
            instagram_posts_summary = self.build_instagram_posts_summary(
                external_data=external_data,
                platforms=platforms,
                start_date=start_date,
                end_date=end_date,
            )
            if instagram_posts_summary:
                external_summaries.append(instagram_posts_summary)

        for item in external_summaries:
            external_summary = self.combine_summaries(external_summary, item, platforms)

        return external_summary, external_platforms

    def compact_meta_ads_row(self, row: Dict[str, Any], metrics: List[str]) -> Dict[str, Any]:
        identity_keys = [
            "id",
            "name",
            "campaignId",
            "campaignName",
            "adsetId",
            "adsetName",
            "objective",
        ]
        compact: Dict[str, Any] = {}
        for key in identity_keys:
            value = row.get(key)
            if value not in (None, ""):
                compact[key] = value
        for metric in metrics:
            if metric in row:
                compact[metric] = round(self.as_number(row.get(metric)), 4)
        return compact

    def top_meta_ads_rows(
        self,
        rows: List[Dict[str, Any]],
        metrics: List[str],
        sort_metric: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        ordered = sorted(
            rows,
            key=lambda item: self.as_number(item.get(sort_metric)),
            reverse=True,
        )
        return [self.compact_meta_ads_row(row, metrics) for row in ordered[:limit]]

    def meta_ads_level_stats(
        self,
        rows: List[Dict[str, Any]],
        metrics: List[str],
    ) -> Dict[str, Any]:
        additive = {
            "investment",
            "impressions",
            "reach",
            "conversationsStarted",
            "leads",
        }
        totals: Dict[str, float] = {}
        averages: Dict[str, float] = {}

        for metric in metrics:
            values = [
                self.as_number(row.get(metric))
                for row in rows
                if row.get(metric) not in (None, "")
            ]
            if not values:
                continue
            if metric in additive:
                totals[metric] = round(float(sum(values)), 4)
            else:
                averages[metric] = round(float(sum(values) / len(values)), 4)

        return {
            "rows": len(rows),
            "totals": totals,
            "averages": averages,
        }

    def build_meta_ads_summary(
        self,
        external_data: Dict[str, Any],
        platforms: List[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        meta_ads = external_data.get("meta_ads") if isinstance(external_data, dict) else None
        if not isinstance(meta_ads, dict):
            meta_ads = external_data if isinstance(external_data, dict) else {}
        if not isinstance(meta_ads, dict) or "campaign" not in meta_ads:
            return None

        campaigns = [row for row in (meta_ads.get("campaign") or []) if isinstance(row, dict)]
        ad_sets = [row for row in (meta_ads.get("adSet") or []) if isinstance(row, dict)]
        ads = [row for row in (meta_ads.get("ad") or []) if isinstance(row, dict)]
        api_summary = meta_ads.get("summary") if isinstance(meta_ads.get("summary"), dict) else {}
        period_raw = meta_ads.get("period") if isinstance(meta_ads.get("period"), dict) else {}

        campaign_metrics = [
            "investment",
            "impressions",
            "reach",
            "frequency",
            "cpm",
            "conversationsStarted",
            "leads",
            "roas",
            "costPerLead",
        ]
        ad_set_metrics = ["investment", "reach", "frequency", "cpm", "ctr"]
        ad_metrics = [
            "impressions",
            "ctr",
            "cpc",
            "cpm",
            "leads",
            "conversationsStarted",
            "costPerLead",
        ]

        selected_metrics = [
            "meta_ads_investment",
            "meta_ads_impressions",
            "meta_ads_reach",
            "meta_ads_frequency",
            "meta_ads_cpm",
            "meta_ads_ctr",
            "meta_ads_cpc",
            "meta_ads_conversations_started",
            "meta_ads_roas",
            "meta_ads_cost_per_lead",
        ]

        kpis: Dict[str, Dict[str, float]] = {}
        for source_key, metric_key in [
            ("investment", "meta_ads_investment"),
            ("impressions", "meta_ads_impressions"),
            ("reach", "meta_ads_reach"),
            ("conversationsStarted", "meta_ads_conversations_started"),
            ("leads", "meta_ads_leads"),
            ("roas", "meta_ads_roas"),
            ("costPerLead", "meta_ads_cost_per_lead"),
        ]:
            if source_key in api_summary:
                kpis[metric_key] = {"sum": round(self.as_number(api_summary.get(source_key)), 4)}

        timings = external_data.get("timings_ms") if isinstance(external_data.get("timings_ms"), dict) else {}
        resource = meta_ads.get("resource") if isinstance(meta_ads.get("resource"), dict) else {}

        return {
            "period": {
                "start": period_raw.get("startDate") or period_raw.get("start") or start_date,
                "end": period_raw.get("endDate") or period_raw.get("end") or end_date,
            },
            "kpis": kpis,
            "anomalies": {},
            "trends": {},
            "segments": {},
            "meta": {
                "platforms": platforms,
                "columns": selected_metrics,
                "selected_metrics": selected_metrics,
                "source_mode": external_data.get("source_mode") or "api_gateway_direct",
                "external_source": external_data.get("source") or "api_gateway",
                "timings_ms": timings,
            },
            "highlights": {
                "meta_ads_campaigns_by_investment": self.top_meta_ads_rows(campaigns, campaign_metrics, "investment"),
                "meta_ads_campaigns_by_conversations": self.top_meta_ads_rows(
                    campaigns,
                    campaign_metrics,
                    "conversationsStarted",
                ),
                "meta_ads_adsets_by_investment": self.top_meta_ads_rows(ad_sets, ad_set_metrics, "investment"),
                "meta_ads_ads_by_impressions": self.top_meta_ads_rows(ads, ad_metrics, "impressions"),
                "meta_ads_ads_by_ctr": self.top_meta_ads_rows(ads, ad_metrics, "ctr"),
            },
            "paid_media": {
                "platform": "meta_ads",
                "resource": {
                    "id": resource.get("id") or meta_ads.get("adAccountId"),
                    "name": resource.get("name"),
                },
                "fetched_at": meta_ads.get("fetchedAt") or external_data.get("fetched_at"),
                "row_counts": {
                    "campaign": len(campaigns),
                    "adSet": len(ad_sets),
                    "ad": len(ads),
                },
                "summary": api_summary,
                "campaign": self.meta_ads_level_stats(campaigns, campaign_metrics),
                "adSet": self.meta_ads_level_stats(ad_sets, ad_set_metrics),
                "ad": self.meta_ads_level_stats(ads, ad_metrics),
            },
        }

    def post_metric_value(self, post: Dict[str, Any], keys: List[str]) -> Any:
        direct = self.first_present(post, keys)
        if direct is not None:
            return direct

        for container_key in ("metrics", "insights"):
            nested = post.get(container_key)
            if isinstance(nested, dict):
                nested_value = self.first_present(nested, keys)
                if nested_value is not None:
                    return nested_value
        return None

    def instagram_post_engagement(self, post: Dict[str, Any]) -> float:
        explicit = self.post_metric_value(post, ["engagement", "engagement_count", "totalEngagement"])
        if explicit is not None:
            return self.as_number(explicit)

        likes = self.as_number(self.post_metric_value(post, ["likes", "like_count", "likeCount"]))
        comments = self.as_number(self.post_metric_value(post, ["comments", "comments_count", "commentsCount"]))
        saves = self.as_number(self.post_metric_value(post, ["saved", "saves", "saved_count"]))
        shares = self.as_number(self.post_metric_value(post, ["shares", "share_count"]))
        return likes + comments + saves + shares

    def compact_instagram_post_row(self, post: Dict[str, Any]) -> Dict[str, Any]:
        caption = self.first_present(post, ["caption", "message", "text"])
        compact: Dict[str, Any] = {
            "id": self.first_present(post, ["id", "media_id", "mediaId"]),
            "created_time": self.first_present(post, ["timestamp", "created_time", "createdTime", "date"]),
            "media_type": self.first_present(post, ["media_type", "mediaType", "type"]),
            "permalink": self.first_present(post, ["permalink", "permalink_url", "url"]),
            "likes": round(self.as_number(self.post_metric_value(post, ["likes", "like_count", "likeCount"])), 4),
            "comments": round(self.as_number(self.post_metric_value(post, ["comments", "comments_count", "commentsCount"])), 4),
            "engagement": round(self.instagram_post_engagement(post), 4),
        }

        for metric_name, keys in {
            "reach": ["reach"],
            "impressions": ["impressions"],
            "saved": ["saved", "saves", "saved_count"],
            "shares": ["shares", "share_count"],
            "views": ["views", "video_views", "plays"],
        }.items():
            value = self.post_metric_value(post, keys)
            if value not in (None, ""):
                compact[metric_name] = round(self.as_number(value), 4)

        if caption:
            compact["caption"] = str(caption).strip()[:240]

        return {key: value for key, value in compact.items() if value not in (None, "")}

    def top_instagram_posts(
        self,
        posts: List[Dict[str, Any]],
        sort_metric: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        metric_keys = {
            "likes": ["likes", "like_count", "likeCount"],
            "comments": ["comments", "comments_count", "commentsCount"],
            "engagement": ["engagement", "engagement_count", "totalEngagement"],
        }

        def sort_value(post: Dict[str, Any]) -> float:
            if sort_metric == "engagement":
                return self.instagram_post_engagement(post)
            return self.as_number(self.post_metric_value(post, metric_keys.get(sort_metric, [sort_metric])))

        ordered = sorted(posts, key=sort_value, reverse=True)
        return [self.compact_instagram_post_row(post) for post in ordered[:limit]]

    def instagram_posts_stats(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        media_types: Dict[str, int] = {}
        totals = {
            "likes": 0.0,
            "comments": 0.0,
            "engagement": 0.0,
            "reach": 0.0,
            "impressions": 0.0,
            "saved": 0.0,
            "shares": 0.0,
            "views": 0.0,
        }

        for post in posts:
            media_type = self.first_present(post, ["media_type", "mediaType", "type"]) or "unknown"
            media_types[str(media_type)] = media_types.get(str(media_type), 0) + 1
            totals["likes"] += self.as_number(self.post_metric_value(post, ["likes", "like_count", "likeCount"]))
            totals["comments"] += self.as_number(self.post_metric_value(post, ["comments", "comments_count", "commentsCount"]))
            totals["engagement"] += self.instagram_post_engagement(post)
            totals["reach"] += self.as_number(self.post_metric_value(post, ["reach"]))
            totals["impressions"] += self.as_number(self.post_metric_value(post, ["impressions"]))
            totals["saved"] += self.as_number(self.post_metric_value(post, ["saved", "saves", "saved_count"]))
            totals["shares"] += self.as_number(self.post_metric_value(post, ["shares", "share_count"]))
            totals["views"] += self.as_number(self.post_metric_value(post, ["views", "video_views", "plays"]))

        row_count = len(posts)
        return {
            "rows": row_count,
            "totals": {key: round(value, 4) for key, value in totals.items()},
            "averages": {
                key: round(value / row_count, 4) if row_count else 0.0
                for key, value in totals.items()
            },
            "media_types": media_types,
        }

    def build_instagram_posts_summary(
        self,
        external_data: Dict[str, Any],
        platforms: List[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        instagram_posts = external_data.get("instagram_posts") if isinstance(external_data, dict) else None
        if not isinstance(instagram_posts, dict):
            return None

        posts_raw = (
            instagram_posts.get("posts")
            or instagram_posts.get("data")
            or instagram_posts.get("items")
            or []
        )
        if not isinstance(posts_raw, list):
            return None
        posts = [post for post in posts_raw if isinstance(post, dict)]

        api_summary = instagram_posts.get("summary") if isinstance(instagram_posts.get("summary"), dict) else {}
        period_raw = instagram_posts.get("period") if isinstance(instagram_posts.get("period"), dict) else {}
        stats = self.instagram_posts_stats(posts)
        totals = stats["totals"]
        averages = stats["averages"]

        total_posts = self.as_number(
            self.first_present(api_summary, ["posts", "totalPosts", "total_posts", "count"])
            if api_summary
            else len(posts)
        ) or float(len(posts))
        total_likes = self.as_number(self.first_present(api_summary, ["likes", "like_count", "totalLikes"])) or totals["likes"]
        total_comments = self.as_number(self.first_present(api_summary, ["comments", "comments_count", "totalComments"])) or totals["comments"]
        total_engagement = self.as_number(self.first_present(api_summary, ["engagement", "totalEngagement"])) or totals["engagement"]
        avg_engagement = (
            self.as_number(self.first_present(api_summary, ["avgEngagementPerPost", "avg_engagement_per_post"]))
            or averages["engagement"]
        )

        selected_metrics = [
            "instagram_posts_count",
            "instagram_posts_likes",
            "instagram_posts_comments",
            "instagram_posts_engagement",
            "instagram_posts_avg_engagement_per_post",
            "instagram_posts_reach",
            "instagram_posts_impressions",
            "instagram_posts_saved",
            "instagram_posts_shares",
            "instagram_posts_views",
        ]

        kpis = {
            "instagram_posts_count": {"sum": round(total_posts, 4)},
            "instagram_posts_likes": {"sum": round(total_likes, 4)},
            "instagram_posts_comments": {"sum": round(total_comments, 4)},
            "instagram_posts_engagement": {"sum": round(total_engagement, 4)},
            "instagram_posts_avg_engagement_per_post": {"mean": round(avg_engagement, 4)},
            "instagram_posts_reach": {"sum": round(totals["reach"], 4)},
            "instagram_posts_impressions": {"sum": round(totals["impressions"], 4)},
            "instagram_posts_saved": {"sum": round(totals["saved"], 4)},
            "instagram_posts_shares": {"sum": round(totals["shares"], 4)},
            "instagram_posts_views": {"sum": round(totals["views"], 4)},
        }

        timings = external_data.get("timings_ms") if isinstance(external_data.get("timings_ms"), dict) else {}
        resource = instagram_posts.get("resource") if isinstance(instagram_posts.get("resource"), dict) else {}

        return {
            "period": {
                "start": period_raw.get("startDate") or period_raw.get("start") or start_date,
                "end": period_raw.get("endDate") or period_raw.get("end") or end_date,
            },
            "kpis": kpis,
            "anomalies": {},
            "trends": {},
            "segments": {},
            "meta": {
                "platforms": platforms,
                "columns": selected_metrics,
                "selected_metrics": selected_metrics,
                "source_mode": external_data.get("source_mode") or "api_gateway_direct",
                "external_source": external_data.get("source") or "api_gateway",
                "timings_ms": timings,
            },
            "highlights": {
                "instagram_posts_by_engagement": self.top_instagram_posts(posts, "engagement"),
                "instagram_posts_by_comments": self.top_instagram_posts(posts, "comments"),
                "instagram_posts_by_likes": self.top_instagram_posts(posts, "likes"),
            },
            "owned_media": {
                "platform": "instagram",
                "resource": {
                    "id": resource.get("id") or instagram_posts.get("igUserId"),
                    "name": resource.get("name") or resource.get("username"),
                },
                "fetched_at": instagram_posts.get("fetchedAt") or external_data.get("fetched_at"),
                "row_counts": {"posts": len(posts)},
                "summary": api_summary,
                "posts": stats,
            },
        }

    def combine_summaries(
        self,
        db_summary: Optional[Dict[str, Any]],
        external_summary: Optional[Dict[str, Any]],
        platforms: List[str],
    ) -> Dict[str, Any]:
        if not db_summary:
            return external_summary or {
                "period": {"start": None, "end": None},
                "kpis": {},
                "anomalies": {},
                "trends": {},
                "segments": {},
                "meta": {"platforms": platforms, "columns": [], "selected_metrics": []},
            }
        if not external_summary:
            db_summary.setdefault("meta", {})["platforms"] = platforms
            return db_summary

        combined = {
            "period": external_summary.get("period") or db_summary.get("period"),
            "kpis": {**(db_summary.get("kpis") or {}), **(external_summary.get("kpis") or {})},
            "anomalies": {**(db_summary.get("anomalies") or {}), **(external_summary.get("anomalies") or {})},
            "trends": {**(db_summary.get("trends") or {}), **(external_summary.get("trends") or {})},
            "segments": {**(db_summary.get("segments") or {}), **(external_summary.get("segments") or {})},
            "highlights": {**(db_summary.get("highlights") or {}), **(external_summary.get("highlights") or {})},
            "period_compare": db_summary.get("period_compare") or {},
            "paid_media": external_summary.get("paid_media") or db_summary.get("paid_media"),
            "owned_media": external_summary.get("owned_media") or db_summary.get("owned_media"),
        }

        db_meta = db_summary.get("meta") or {}
        ext_meta = external_summary.get("meta") or {}
        selected = list(dict.fromkeys([
            *(db_meta.get("selected_metrics") or []),
            *(ext_meta.get("selected_metrics") or []),
        ]))
        columns = list(dict.fromkeys([
            *(db_meta.get("columns") or []),
            *(ext_meta.get("columns") or []),
        ]))
        combined["meta"] = {
            **db_meta,
            **ext_meta,
            "platforms": platforms,
            "columns": columns,
            "selected_metrics": selected,
            "source_mode": ext_meta.get("source_mode"),
        }
        return combined
