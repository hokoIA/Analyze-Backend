from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import os
import numpy as np
import pandas as pd
from utils.db.relational_db import RelationalDBManager
from utils.db.vector_db import VectorDBManager
from utils.prompts.system_prompts import (
    get_platform_prompt,
    get_analysis_prompt,
    build_narrative_prompt,
    build_chat_system_prompt
)

# ChatOpenAI (corrigido conforme aviso de depreciação)
try:
    from langchain_community.chat_models import ChatOpenAI  # pip install -U langchain-community
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore


# === Mapeamento canônico por plataforma ===
PLATFORM_SCHEMA = {
    "instagram": {
        # origem -> canônico
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
        "followers": "followers"
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
    }
}
# Métricas priorizadas (agora inclui GA)
PREFERRED_BASES = (
    "reach", "views", "impressions", "followers",
    "traffic_direct", "traffic_organic_search", "traffic_organic_social", "search_volume",
    "investment", "frequency", "cpm", "ctr", "cpc", "conversations_started", "roas", "cost_per_lead"
)


# =============================
# Helpers de normalização / core
# =============================

def _normalize_platform_df(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = df.copy()

    # 1) Uniformizar nome da coluna de data
    if "data" not in out.columns and "date" in out.columns:
        out = out.rename(columns={"date": "data"})

    # 2) Remover campos técnicos que não serão agregados por dia
    drop_candidates = [c for c in out.columns if c.lower() in {"id_customer", "agency_id", "client_id"}]
    if drop_candidates:
        out = out.drop(columns=drop_candidates, errors="ignore")

    # 3) Aplicar mapeamento canônico específico da plataforma
    schema = PLATFORM_SCHEMA.get(platform, {})
    out = out.rename(columns={orig: canon for orig, canon in schema.items() if orig in out.columns})

    # 4) Prefixar com o nome da plataforma, preservando 'data'
    ren = {}
    for col in out.columns:
        if col == "data":
            continue
        if not col.startswith(f"{platform}_"):
            ren[col] = f"{platform}_{col}"
    if ren:
        out = out.rename(columns=ren)

    return out

def _prepare_dates(df: pd.DataFrame, tz: str = "America/Sao_Paulo") -> pd.DataFrame:
    """
    Garante 'data' normalizada ao dia (sem deslocar quando a origem é apenas YYYY-MM-DD).
    - Se vier timezone-aware, converte para tz local e remove tz.
    - Se vier naive (somente data), apenas normaliza.
    """
    out = df.copy()
    s = pd.to_datetime(out["data"], errors="coerce")

    # Se a série tiver timezone (alguns itens podem ser tz-aware, outros não)
    if getattr(s.dt, "tz", None) is not None:
        s = s.dt.tz_convert(tz).dt.tz_localize(None)

    out["data"] = s.dt.normalize()
    out = out.sort_values("data").reset_index(drop=True)
    return out

def _basic_kpis(df: pd.DataFrame, cols: List[str]) -> Dict[str, Dict[str, float]]:
    kpis: Dict[str, Dict[str, float]] = {}
    for c in cols:
        if c in df.columns:
            s = df[c].fillna(0)
            kpis[c] = {
                "mean": float(s.mean()),
                "median": float(s.median()),
                "p95": float(s.quantile(0.95)),
                "sum": float(s.sum()),
                "non_zero_days": float((s > 0).sum()),
                "days": float(s.shape[0]),
            }
    return kpis

def _mad_anomalies(df: pd.DataFrame, col: str, zcut: float = 3.0) -> List[Dict[str, Any]]:
    if col not in df.columns:
        return []
    # Mantém apenas valores numéricos válidos; ausentes após merge entre plataformas
    # não devem virar outliers nem ser convertidos para float.
    s = pd.to_numeric(df[col], errors="coerce")
    valid_mask = s.notna()
    if valid_mask.sum() == 0:
        return []
    s_valid = s.loc[valid_mask]
    med = s_valid.median()
    mad = (s_valid - med).abs().median()
    if mad == 0 or pd.isna(mad):
        return []

    z = 0.6745 * (s_valid - med) / mad
    outlier_idx = z.loc[z.abs() >= zcut].index
    outliers = df.loc[outlier_idx, ["data", col]].copy()
    outliers[col] = pd.to_numeric(outliers[col], errors="coerce")
    outliers = outliers.dropna(subset=["data", col])

    records: List[Dict[str, Any]] = []
    for _, row in outliers.iterrows():
        records.append({"data": str(row["data"].date()), col: float(row[col])})
    return records

def _dod_change_mean(df: pd.DataFrame, col: str) -> Optional[float]:
    if col not in df.columns:
        return None
    s = df[col].fillna(0)
    pct = s.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    return float(pct.mean()) if not pct.empty else None

def _weekday_breakdown(df: pd.DataFrame, col: str) -> List[Dict[str, Any]]:
    if col not in df.columns or "data" not in df.columns:
        return []
    tmp = df.copy()
    try:
        tmp["weekday"] = tmp["data"].dt.day_name(locale="pt_BR")
    except Exception:
        wd_map = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
        tmp["weekday"] = tmp["data"].dt.day_of_week.map(wd_map)
    g = tmp.groupby("weekday")[col].agg(["mean", "sum", "median"]).reset_index()
    records: List[Dict[str, Any]] = []
    for _, row in g.iterrows():
        records.append({
            "weekday": str(row["weekday"]),
            "mean": float(row["mean"]),
            "sum": float(row["sum"]),
            "median": float(row["median"]),
        })
    return records

# =============================
# Config/DTOs
# =============================

@dataclass
class AnalysisPayload:
    agency_id: str
    client_id: str
    platforms: List[str]
    analysis_focus: str = "panorama"  # "branding" | "negocio" | "conexao" | "panorama"
    analysis_type: str = "descriptive"  # 'descriptive' | 'predictive' | 'prescriptive' | 'general'
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD
    output_format: str = "detalhado"
    analysis_query: Optional[str] = None  # permite sobrescrever a pergunta ao LLM
    bilingual: bool = True  # redige mentalmente em EN e entrega PT-BR
    granularity: str = "detalhada"
    voice_profile: str = "CMO"
    decision_mode: str = "decision_brief"
    narrative_style: str = "SCQA"
    source_mode: Optional[str] = None
    external_data: Optional[Dict[str, Any]] = None


# =============================
# Classe principal
# =============================

class AdvancedDataAnalyst:
    def __init__(self,
                 vector_db: Optional[VectorDBManager] = None,
                 relational_db: Optional[RelationalDBManager] = None,
                 openai_api_key: Optional[str] = None,
                 pinecone_api_key: Optional[str] = None,
                 ):
        # Injeta dependências reais ou cria com variáveis de ambiente
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.vector_db = vector_db or VectorDBManager(
            pinecone_api_key=pinecone_api_key or os.getenv("PINECONE_API_KEY", ""),
            openai_api_key=self.openai_api_key or ""
        )
        self.rel_db = relational_db or RelationalDBManager()
        self.clients_cache: Dict[str, Dict[str, Any]] = {}

    # --------- Data loading ---------
    def _load_platform_df(self,
                          agency_id: str,
                          client_id: str,
                          platform: str,
                          start_date: Optional[str],
                          end_date: Optional[str]) -> pd.DataFrame:
        """
        Usa RelationalDBManager.get_client_data para obter dados (coluna obrigatória 'data').
        """
        try:
            df = self.rel_db.get_client_data(
                client_id=client_id,
                platform=platform,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception:
            # Se não houver dados, devolve DF vazio com 'data'
            return pd.DataFrame({"data": []})

        if df is None or df.empty:
            return pd.DataFrame({"data": []})

        df = _normalize_platform_df(df, platform)
        df = _prepare_dates(df)
        return df

    def _merge_platform_dfs(self, dfs: List[pd.DataFrame]) -> pd.DataFrame:
        if not dfs:
            return pd.DataFrame({"data": []})
        merged = dfs[0]
        for add in dfs[1:]:
            merged = pd.merge(merged, add, on="data", how="outer")
        merged = merged.sort_values("data").reset_index(drop=True)
        return merged

    # --------- Deterministic analytics ---------
    def _compute_summary(self, merged_df: pd.DataFrame, platforms: List[str]) -> Dict[str, Any]:
        all_cols = merged_df.columns.tolist()
        metric_cols = [c for c in all_cols if c != "data"]

        # Selecionar métricas canônicas por plataforma
        candidatos: List[str] = []
        for base in PREFERRED_BASES:
            for p in platforms:
                pc = f"{p}_{base}"
                if pc in merged_df.columns:
                    candidatos.append(pc)

        if not candidatos:
            candidatos = metric_cols

        summary: Dict[str, Any] = {
            "period": {
                "start": str(merged_df["data"].min().date()) if not merged_df.empty else None,
                "end": str(merged_df["data"].max().date()) if not merged_df.empty else None,
            },
            "kpis": _basic_kpis(merged_df, candidatos),
            "anomalies": {c: _mad_anomalies(merged_df, c) for c in candidatos},
            "trends": {f"{c}_dod_mean": _dod_change_mean(merged_df, c) for c in candidatos},
            "segments": {f"{c}_by_weekday": _weekday_breakdown(merged_df, c) for c in candidatos},
            "meta": {"platforms": platforms, "columns": all_cols, "selected_metrics": candidatos},
        }

        # ---- Highlights: top 3 por métrica ----
        highlights = {}
        for c in candidatos:
            dfc = merged_df[["data", c]].dropna()
            if dfc.empty: 
                continue
            top3 = dfc.sort_values(c, ascending=False).head(3)
            highlights[c] = [
                {"date": str(r["data"].date()), "value": float(r[c])}
                for _, r in top3.iterrows()
            ]
        summary["highlights"] = highlights

        # ---- Comparação com período anterior (mesma duração) ----
        try:
            import pandas as pd
            period = summary["period"]
            if period["start"] and period["end"]:
                start = pd.to_datetime(period["start"])
                end   = pd.to_datetime(period["end"])
                delta = (end - start) or pd.Timedelta(days=1)
                prev_start, prev_end = start - delta, start
                prev_mask = (merged_df["data"] >= prev_start) & (merged_df["data"] < prev_end)
                cur_mask  = (merged_df["data"] >= start)      & (merged_df["data"] <= end)
                comp = {}
                for c in candidatos:
                    cur  = merged_df.loc[cur_mask, c].mean()
                    prev = merged_df.loc[prev_mask, c].mean()
                    if pd.notna(cur) and pd.notna(prev) and prev != 0:
                        comp[c] = {"cur": float(cur), "prev": float(prev), "delta_pct": float((cur/prev) - 1)}
                summary["period_compare"] = comp
        except Exception:
            pass

        # ---- Variância “baixa|media|alta” para gating de few-shots ----
        try:
            import numpy as np
            variances = []
            for c in candidatos:
                s = merged_df[c].dropna()
                if len(s) > 3:
                    variances.append(float(np.var(s)))
            vh = "baixa"
            if variances:
                q3 = np.quantile(variances, 0.75)
                q1 = np.quantile(variances, 0.25)
                vh = "alta" if q3 > 0 and (q3 - q1) > 0 else "media"
            summary["meta"]["variance_hint"] = vh
        except Exception:
            summary["meta"]["variance_hint"] = "media"

        return summary

    def _enrich_summary(self, merged_df, platforms, summary):
        """
        Enriquecimento mínimo (Opção A):
        - highlights: top 3 valores por métrica com a data
        - meta.variance_hint: 'baixa' | 'media' | 'alta' (gating de few-shots)
        Não mexe no _compute_summary. É chamado depois.
        """
        import numpy as np
        import pandas as pd

        if "data" in merged_df.columns:
            merged_df = merged_df.copy()
            merged_df["data"] = pd.to_datetime(merged_df["data"], errors="coerce")
            merged_df = merged_df.dropna(subset=["data"]).sort_values("data")

        # Escolhe métricas numéricas (todas colunas exceto 'data')
        metric_cols = []
        for c in merged_df.columns:
            if c == "data":
                continue
            try:
                if np.issubdtype(merged_df[c].dtype, np.number):
                    metric_cols.append(c)
            except Exception:
                # Se dtype der erro/objeto, ignora
                pass

        # 1) Highlights: top 3 por métrica com data
        highlights = {}
        for c in metric_cols:
            dfc = merged_df[["data", c]].dropna()
            if dfc.empty:
                continue
            top3 = dfc.sort_values(c, ascending=False).head(3)
            highlights[c] = [
                {"date": d.strftime("%Y-%m-%d"), "value": float(v)}
                for d, v in zip(top3["data"], top3[c])
            ]
        summary["highlights"] = highlights

        # 2) Variance hint: para gating de few-shots (evitar "picos inventados")
        try:
            variances = []
            for c in metric_cols:
                s = merged_df[c].dropna().values
                if s.size > 3:
                    variances.append(float(np.var(s)))
            vh = "media"
            if variances:
                q1, q3 = np.percentile(variances, [25, 75])
                vh = "alta" if (q3 - q1) > 0 else "baixa"
            summary.setdefault("meta", {})["variance_hint"] = vh
        except Exception:
            summary.setdefault("meta", {})["variance_hint"] = "media"

        return summary

    # --------- Narrative (LLM) ---------
    def _make_narrative(self,
                        platforms: List[str],
                        analysis_type: str,
                        analysis_query: str,
                        context_text: str,
                        summary: Dict[str, Any],
                        output_format: str = "detalhado",
                        bilingual: bool = True) -> str:
        """
        Monta as mensagens para o LLM com:
        - system: identidade + voz + foco (build_chat_system_prompt)
        - user: instruções completas + [DADOS] + [CONTEXTO] (build_narrative_prompt)
        """
        system_content = build_chat_system_prompt(
            client_name=getattr(self, "client_name", "Cliente"),
            voice_profile=getattr(self, "voice_profile", "CMO"),
            analysis_focus=getattr(self, "analysis_focus", "panorama"),
        )
        user_content = build_narrative_prompt(
            platforms=platforms,
            analysis_type=analysis_type,
            analysis_focus=getattr(self, "analysis_focus", "panorama"),
            analysis_query=analysis_query,
            context_text=context_text,
            summary_json=summary,
            output_format=output_format,
            granularity=getattr(self, "current_granularity", "detalhada"),
            bilingual=bilingual,
            voice_profile=getattr(self, "voice_profile", "CMO"),
            decision_mode=getattr(self, "decision_mode", "decision_brief"),
            narrative_style=getattr(self, "narrative_style", "SCQA"),
        )
        if ChatOpenAI is None:
            return (
                "[Aviso: ChatOpenAI indisponível no ambiente]\n\n"
                "Resumo JSON:\n" + str(summary) + "\n\n"
                "Solicitação:\n" + analysis_query + "\n\n"
                "(Nesta etapa, um LLM redigiria a narrativa com base no JSON e contexto acima.)"
            )

        # Config mais adequada para narrativa: criatividade moderada, pouca repetição
        llm = ChatOpenAI(
            model="gpt-4.1",
            temperature=0.7,
            presence_penalty=0.1,
            frequency_penalty=0.1,
            api_key=self.openai_api_key,
        )

        msgs = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        first = llm.invoke(msgs).content  # type: ignore

        refined = self._refine_if_generic(llm, first, summary, user_content)
        return self._postprocess_output(refined, output_format)

    def _refine_if_generic(self, llm, text: str, summary: Dict[str, Any], user_content: str) -> str:
        import re, json
        # heurísticas simples:
        # - se não tiver NENHUM número ou data, pedir revisão focando em datas/números do JSON
        has_number = bool(re.search(r"\d{2}/\d{2}|\d{4}-\d{2}-\d{2}|\b\d{2,}[.,]?\d*\b", text))
        has_date   = bool(re.search(r"\b\d{1,2}/\d{1,2}\b|\b\d{4}-\d{2}-\d{2}\b", text))
        if has_number and has_date:
            return text

        refine_prompt = (
            "Revise o texto abaixo: ele está genérico. Reescreva citando datas e números concretos do JSON a seguir, "
            "sempre que isso ajudar a explicar o movimento dos dados.\n\n"
            "[TEXTO]\n" + text + "\n\n"
            "[DADOS]\n" + json.dumps(summary, ensure_ascii=False)
        )
        out = llm.invoke(
            [
                {"role": "system", "content": "Você é um editor sênior objetivo e técnico."},
                {"role": "user", "content": refine_prompt},
            ]
        ).content
        return out or text

    def _postprocess_output(self, text: str, output_format: str) -> str:
        """
        Ajustes finais para aderir ao formato pedido:
        - "topicos": garante lista em bullets se o modelo não fizer.
        - "resumido": corta para poucas frases se vier longo demais.
        """
        import re

        fmt = (output_format or "detalhado").strip().lower()
        cleaned = text.strip()

        if fmt == "topicos":
            # Se já houver bullets, mantém como está
            lines = cleaned.splitlines()
            has_bullets = any(l.lstrip().startswith(("-", "*", "•")) for l in lines)
            if has_bullets:
                return cleaned

            # Caso contrário, transforma frases em bullets
            sentences = re.split(r'(?<=[.!?])\s+', cleaned)
            bullets = [f"- {s.strip()}" for s in sentences if s.strip()]
            # Evita criar lista gigantesca
            if len(bullets) > 10:
                bullets = bullets[:10]
            return "\n".join(bullets)

        if fmt == "resumido":
            # Mantém só as primeiras 4–5 frases para forçar concisão
            sentences = re.split(r'(?<=[.!?])\s+', cleaned)
            if len(sentences) > 5:
                cleaned = " ".join(sentences[:5]).strip()
            return cleaned

        # detalhado / default → sem ajuste estrutural
        return cleaned

    # --------- Public API ---------
    def _build_rag_query(self,
                        analysis_query: str,
                        platforms: List[str],
                        summary: Dict[str, Any],
                        analysis_type: str,
                        analysis_focus: str) -> str:
        """
        Monta uma query mais rica para o RAG, combinando:
        - pergunta original do usuário
        - tipo de análise + foco (branding/negócio/conexão/panorama)
        - principais métricas e métricas com anomalias
        """
        parts: List[str] = []

        if analysis_query:
            parts.append(analysis_query.strip())

        atype = (analysis_type or "descriptive").strip().lower()
        parts.append(f"tipo={atype}")
        parts.append(f"foco={analysis_focus or 'panorama'}")

        # Meta: métricas selecionadas (já vem do summary)
        if isinstance(summary, dict):
            meta = summary.get("meta", {}) or {}
            selected = meta.get("selected_metrics") or []
            if selected:
                parts.append("metricas-chave: " + ", ".join(selected[:6]))

            # Métricas com anomalias (picos/vales)
            anomalies = summary.get("anomalies", {}) or {}
            hot_metrics = [m for m, vals in anomalies.items() if vals]
            if hot_metrics:
                parts.append("metricas-com-picos: " + ", ".join(hot_metrics[:6]))

        # Plataformas envolvidas
        if platforms:
            parts.append("plataformas: " + ", ".join(platforms))

        return " | ".join(parts)

    def _as_number(self, value: Any) -> float:
        try:
            if value is None or value == "":
                return 0.0
            n = float(value)
            return n if np.isfinite(n) else 0.0
        except Exception:
            return 0.0

    def _compact_meta_ads_row(self, row: Dict[str, Any], metrics: List[str]) -> Dict[str, Any]:
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
                compact[metric] = round(self._as_number(row.get(metric)), 4)
        return compact

    def _top_meta_ads_rows(
        self,
        rows: List[Dict[str, Any]],
        metrics: List[str],
        sort_metric: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if not rows:
            return []
        ordered = sorted(
            rows,
            key=lambda item: self._as_number(item.get(sort_metric)),
            reverse=True,
        )
        return [self._compact_meta_ads_row(row, metrics) for row in ordered[:limit]]

    def _meta_ads_level_stats(
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
                self._as_number(row.get(metric))
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

    def _build_meta_ads_external_summary(
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
                kpis[metric_key] = {"sum": round(self._as_number(api_summary.get(source_key)), 4)}

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
                "meta_ads_campaigns_by_investment": self._top_meta_ads_rows(
                    campaigns,
                    campaign_metrics,
                    "investment",
                ),
                "meta_ads_campaigns_by_conversations": self._top_meta_ads_rows(
                    campaigns,
                    campaign_metrics,
                    "conversationsStarted",
                ),
                "meta_ads_adsets_by_investment": self._top_meta_ads_rows(
                    ad_sets,
                    ad_set_metrics,
                    "investment",
                ),
                "meta_ads_ads_by_impressions": self._top_meta_ads_rows(
                    ads,
                    ad_metrics,
                    "impressions",
                ),
                "meta_ads_ads_by_ctr": self._top_meta_ads_rows(
                    ads,
                    ad_metrics,
                    "ctr",
                ),
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
                "campaign": self._meta_ads_level_stats(campaigns, campaign_metrics),
                "adSet": self._meta_ads_level_stats(ad_sets, ad_set_metrics),
                "ad": self._meta_ads_level_stats(ads, ad_metrics),
            },
        }

    def _combine_summaries(
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
            "paid_media": external_summary.get("paid_media"),
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

    def get_client_agent(self,
                         agency_id: str,
                         client_id: str,
                         platforms: List[str],
                         start_date: Optional[str],
                         end_date: Optional[str],
                         external_data: Optional[Dict[str, Any]] = None) -> Callable[[str, str, bool], Dict[str, Any]]:
        external_summary = None
        external_platforms: List[str] = []
        if isinstance(external_data, dict):
            external_summary = self._build_meta_ads_external_summary(
                external_data=external_data,
                platforms=platforms,
                start_date=start_date,
                end_date=end_date,
            )
            if external_summary:
                external_platforms.append("meta_ads")

        db_platforms = [p for p in platforms if p not in external_platforms]

        # 1) Carregar e normalizar DFs por plataforma
        dfs: List[pd.DataFrame] = []
        for p in db_platforms:
            dfp = self._load_platform_df(agency_id, client_id, p, start_date, end_date)
            if not dfp.empty:
                dfs.append(dfp)
        merged_df = self._merge_platform_dfs(dfs)

        # 2) Computar resumo determinístico
        db_summary = None
        if db_platforms:
            db_summary = self._compute_summary(merged_df, db_platforms)
            db_summary = self._enrich_summary(merged_df, db_platforms, db_summary)
        summary = self._combine_summaries(db_summary, external_summary, platforms)

        # 3) Cache por cliente + plataformas + período
        key_platforms = "_".join(sorted(platforms))
        cache_key = f"{client_id}_{key_platforms}_{summary['period']['start']}_{summary['period']['end']}"

        self.clients_cache[cache_key] = {
            "df": merged_df,
            "summary": summary,
            "ts": datetime.now().isoformat(),
        }

        # 4) Retornar função de invocação que busca contexto + narra
        def _invoke(analysis_query: str, output_format: str = "detalhado", bilingual: bool = True) -> Dict[str, Any]:
            # Tipo/foco corrente vindos do run_analysis
            atype = self.current_analysis_type if hasattr(self, "current_analysis_type") else "descriptive"
            focus = getattr(self, "analysis_focus", "panorama")

            # 4.1) Montar query enriquecida para o RAG
            rag_query = self._build_rag_query(
                analysis_query=analysis_query or "panorama do período",
                platforms=platforms,
                summary=summary,
                analysis_type=atype,
                analysis_focus=focus,
            )

            # 4.2) Buscar contexto histórico no Pinecone
            context_text = self.vector_db.retrieve_context_for_analysis(
                query=rag_query,
                scope="client",
                agency_id=agency_id,
                client_id=client_id,
                k_total=8,
            )

            # 4.3) Gerar narrativa (LLM apenas redige)
            analysis_text = self._make_narrative(
                platforms=platforms,
                analysis_type=atype,
                analysis_query=analysis_query,
                context_text=context_text,
                summary=summary,
                output_format=output_format,
                bilingual=bilingual,
            )
            return {"summary": summary, "analysis": analysis_text}

        return _invoke

    def run_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        start_time = datetime.now()
        raw_platforms = payload.get("platforms") or []
        platforms_list = [str(p) for p in raw_platforms]

        # >>> regra: se não vier tipo de análise e foco for NEGÓCIO,
        # >>> usar "general" (análise integrada: descritiva + preditiva + prescritiva)
        analysis_focus_raw = str(payload.get("analysis_focus") or "panorama")
        analysis_type_raw = payload.get("analysis_type")
        if not analysis_type_raw and analysis_focus_raw == "negocio":
            analysis_type_raw = "general"

        ap = AnalysisPayload(
            agency_id=str(payload.get("agency_id") or ""),
            client_id=str(payload.get("client_id") or ""),
            platforms=platforms_list,
            analysis_focus=str(payload.get("analysis_focus") or "panorama"),
            analysis_type=str(payload.get("analysis_type") or "descriptive"),
            start_date=payload.get("start_date") or None,
            end_date=payload.get("end_date") or None,
            output_format=str(payload.get("output_format") or "detalhado"),
            analysis_query=payload.get("analysis_query") or None,
            bilingual=bool(payload.get("bilingual", True)),
            granularity=str(payload.get("granularity") or payload.get("output_granularity") or "detalhada"),
            voice_profile=str(payload.get("voice_profile") or "CMO"),
            decision_mode=str(payload.get("decision_mode") or "decision_brief"),
            narrative_style=str(payload.get("narrative_style") or "SCQA"),
            source_mode=payload.get("source_mode") or None,
            external_data=payload.get("external_data") if isinstance(payload.get("external_data"), dict) else None,
        )

        # Normaliza o decision_mode a partir do output_format escolhido na UI
        fmt = (ap.output_format or "detalhado").strip().lower()

        if fmt == "resumido":
            ap.decision_mode = "decision_brief"
        elif fmt == "topicos":
            ap.decision_mode = "topicos"
        else:
            ap.decision_mode = "narrativa"


        # Guardar o tipo de análise corrente para o _invoke usar
        self.voice_profile = ap.voice_profile
        self.decision_mode = ap.decision_mode
        self.narrative_style = ap.narrative_style
        self.current_analysis_type = ap.analysis_type
        self.current_granularity = ap.granularity
        self.analysis_focus = ap.analysis_focus

        invoke_func = self.get_client_agent(
            agency_id=ap.agency_id,
            client_id=ap.client_id,
            platforms=ap.platforms,
            start_date=ap.start_date,
            end_date=ap.end_date,
            external_data=ap.external_data,
        )

        # Se não vier pergunta específica, monta uma a partir dos templates
        if not ap.analysis_query:
            if ap.analysis_focus == "negocio":
                ap.analysis_query = (
                    "Quero uma análise de negócio completa para este cliente, "
                    "combinando visão descritiva, preditiva e prescritiva em um único texto. "
                    "Foque em receita, margens, eficiência, riscos e oportunidades do negócio, dentre outros o que achar significativo falar e sem economizar texto, raciocínio ou análise, "
                    "usando o máximo possível de números e valores disponíveis nos dados, "
                    "sem se prender a plataformas específicas."
                )
            else:
                date_filter = ""
                if ap.start_date and ap.end_date:
                    date_filter = f" no período de {ap.start_date} a {ap.end_date}"
                elif ap.start_date:
                    date_filter = f" a partir de {ap.start_date}"
                elif ap.end_date:
                    date_filter = f" até {ap.end_date}"
                ap.analysis_query = get_analysis_prompt(ap.analysis_type, ap.platforms, date_filter)
        try:
            result = invoke_func(ap.analysis_query, ap.output_format, ap.bilingual)
            status = "success"
            error = None
        except Exception as e:  # pragma: no cover
            result = {"summary": None, "analysis": f"Falha na análise: {str(e)}"}
            status = "error"
            error = str(e)

        end_time = datetime.now()
        response_json_return = {
            "agency_id": ap.agency_id,
            "client_id": ap.client_id,
            "platforms": ap.platforms,
            "analysis_type": ap.analysis_type,
            "query": ap.analysis_query,
            "summary": result.get("summary"),
            "result": result.get("analysis"),
            "execution_time": (end_time - start_time).total_seconds(),
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "error": error,
        }
        return response_json_return
