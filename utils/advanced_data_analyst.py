from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
import os
import pandas as pd
from utils.db.relational_db import RelationalDBManager
from utils.db.vector_db import VectorDBManager
from utils.dataframe import PlatformDataFrameNormalizer
from utils.debug.prompt_debug_logger import PromptDebugLogger
from utils.external_data import ExternalDataSummaryBuilder
from utils.llm.config import get_llm_config
from utils.narrative import AnalysisNarrativeService
from utils.prompts.system_prompts import (
    get_platform_prompt,
    get_analysis_prompt,
    get_business_analysis_query,
)
from utils.rag import RAGQueryBuilder
from utils.summary import OrganicSummaryBuilder

# ChatOpenAI (corrigido conforme aviso de depreciação)
try:
    from langchain_community.chat_models import ChatOpenAI  # pip install -U langchain-community
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore


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
        self.llm_config = get_llm_config()
        self.dataframe_normalizer = PlatformDataFrameNormalizer()
        self.external_summary_builder = ExternalDataSummaryBuilder()
        self.rag_query_builder = RAGQueryBuilder()
        self.organic_summary_builder = OrganicSummaryBuilder()
        self.debug_logger = PromptDebugLogger()
        self.narrative_service = AnalysisNarrativeService(
            llm_config=self.llm_config,
            openai_api_key=self.openai_api_key,
            chat_model_cls=ChatOpenAI,
            debug_logger=self.debug_logger,
        )

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

        return self.dataframe_normalizer.normalize(df, platform)

    def _merge_platform_dfs(self, dfs: List[pd.DataFrame]) -> pd.DataFrame:
        return self.dataframe_normalizer.merge(dfs)

    # --------- Deterministic analytics ---------
    # --------- Narrative (LLM) ---------
    def _make_narrative(self,
                        platforms: List[str],
                        analysis_type: str,
                        analysis_query: str,
                        context_text: str,
                        summary: Dict[str, Any],
                        output_format: str = "detalhado",
                        bilingual: bool = True,
                        debug_request_id: Optional[str] = None) -> str:
        return self.narrative_service.generate(
            platforms=platforms,
            analysis_type=analysis_type,
            analysis_query=analysis_query,
            context_text=context_text,
            summary=summary,
            output_format=output_format,
            bilingual=bilingual,
            client_name=getattr(self, "client_name", "Cliente"),
            voice_profile=getattr(self, "voice_profile", "CMO"),
            analysis_focus=getattr(self, "analysis_focus", "panorama"),
            granularity=getattr(self, "current_granularity", "detalhada"),
            decision_mode=getattr(self, "decision_mode", "decision_brief"),
            narrative_style=getattr(self, "narrative_style", "SCQA"),
            debug_request_id=debug_request_id,
        )

    # --------- Public API ---------
    def get_client_agent(self,
                         agency_id: str,
                         client_id: str,
                         platforms: List[str],
                         start_date: Optional[str],
                         end_date: Optional[str],
                         external_data: Optional[Dict[str, Any]] = None,
                         debug_request_id: Optional[str] = None) -> Callable[[str, str, bool], Dict[str, Any]]:
        self.debug_logger.log_json(
            "analysis_external_data_received",
            external_data or {},
            request_id=debug_request_id,
        )
        external_summary, external_platforms = self.external_summary_builder.build(
            external_data=external_data,
            platforms=platforms,
            start_date=start_date,
            end_date=end_date,
        )
        self.debug_logger.log_json(
            "analysis_external_summary_built",
            {
                "external_platforms": external_platforms,
                "external_summary": external_summary,
            },
            request_id=debug_request_id,
        )

        db_platforms = [p for p in platforms if p not in external_platforms]

        # 1) Carregar e normalizar DFs por plataforma
        dfs: List[pd.DataFrame] = []
        for p in db_platforms:
            dfp = self._load_platform_df(agency_id, client_id, p, start_date, end_date)
            self.debug_logger.log_json(
                "analysis_db_platform_dataframe",
                {
                    "platform": p,
                    "rows": int(len(dfp.index)),
                    "columns": list(dfp.columns),
                    "data": dfp.to_dict(orient="records"),
                },
                request_id=debug_request_id,
            )
            if not dfp.empty:
                dfs.append(dfp)
        merged_df = self._merge_platform_dfs(dfs)
        self.debug_logger.log_json(
            "analysis_merged_dataframe",
            {
                "rows": int(len(merged_df.index)),
                "columns": list(merged_df.columns),
                "data": merged_df.to_dict(orient="records"),
            },
            request_id=debug_request_id,
        )

        # 2) Computar resumo determinístico
        db_summary = None
        if db_platforms:
            db_summary = self.organic_summary_builder.build(merged_df, db_platforms)
        summary = self.external_summary_builder.combine_summaries(db_summary, external_summary, platforms)
        self.debug_logger.log_json(
            "analysis_final_summary_sent_to_prompt",
            summary,
            request_id=debug_request_id,
        )

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
            rag_query = self.rag_query_builder.build(
                analysis_query=analysis_query or "panorama do período",
                platforms=platforms,
                summary=summary,
                analysis_type=atype,
                analysis_focus=focus,
            )
            self.debug_logger.log_text(
                "analysis_rag_query",
                rag_query,
                request_id=debug_request_id,
            )

            # 4.2) Buscar contexto histórico no Pinecone
            context_text = self.vector_db.retrieve_context_for_analysis(
                query=rag_query,
                scope="client",
                agency_id=agency_id,
                client_id=client_id,
                k_total=8,
            )
            self.debug_logger.log_text(
                "analysis_rag_context_retrieved",
                context_text,
                request_id=debug_request_id,
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
                debug_request_id=debug_request_id,
            )
            return {"summary": summary, "analysis": analysis_text}

        return _invoke

    def run_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        start_time = datetime.now()
        debug_request_id = f"analysis-{uuid4()}"
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

        self.debug_logger.log_json(
            "analysis_request_received",
            {
                "request_id": debug_request_id,
                "agency_id": ap.agency_id,
                "client_id": ap.client_id,
                "platforms": ap.platforms,
                "analysis_focus": ap.analysis_focus,
                "analysis_type": ap.analysis_type,
                "start_date": ap.start_date,
                "end_date": ap.end_date,
                "output_format": ap.output_format,
                "granularity": ap.granularity,
                "voice_profile": ap.voice_profile,
                "decision_mode": ap.decision_mode,
                "narrative_style": ap.narrative_style,
                "source_mode": ap.source_mode,
                "analysis_query": ap.analysis_query,
            },
            request_id=debug_request_id,
        )


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
            debug_request_id=debug_request_id,
        )

        # Se não vier pergunta específica, monta uma a partir dos templates
        if not ap.analysis_query:
            if ap.analysis_focus == "negocio":
                ap.analysis_query = get_business_analysis_query()
            else:
                date_filter = ""
                if ap.start_date and ap.end_date:
                    date_filter = f" no período de {ap.start_date} a {ap.end_date}"
                elif ap.start_date:
                    date_filter = f" a partir de {ap.start_date}"
                elif ap.end_date:
                    date_filter = f" até {ap.end_date}"
                ap.analysis_query = get_analysis_prompt(ap.analysis_type, ap.platforms, date_filter)
        self.debug_logger.log_text(
            "analysis_effective_user_query",
            ap.analysis_query or "",
            request_id=debug_request_id,
        )
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
