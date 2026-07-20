from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from utils.llm.config import LLMConfig
from utils.prompts.system_prompts import (
    build_chat_system_prompt,
    build_narrative_prompt,
    render_refine_prompt,
)


class AnalysisNarrativeService:
    def __init__(
        self,
        llm_config: LLMConfig,
        openai_api_key: Optional[str],
        chat_model_cls: Optional[Callable[..., Any]],
    ):
        self.llm_config = llm_config
        self.openai_api_key = openai_api_key
        self.chat_model_cls = chat_model_cls

    def generate(
        self,
        platforms: List[str],
        analysis_type: str,
        analysis_query: str,
        context_text: str,
        summary: Dict[str, Any],
        output_format: str = "detalhado",
        bilingual: bool = True,
        client_name: str = "Cliente",
        voice_profile: str = "CMO",
        analysis_focus: str = "panorama",
        granularity: str = "detalhada",
        decision_mode: str = "decision_brief",
        narrative_style: str = "SCQA",
    ) -> str:
        system_content = build_chat_system_prompt(
            client_name=client_name,
            voice_profile=voice_profile,
            analysis_focus=analysis_focus,
        )
        user_content = build_narrative_prompt(
            platforms=platforms,
            analysis_type=analysis_type,
            analysis_focus=analysis_focus,
            analysis_query=analysis_query,
            context_text=context_text,
            summary_json=summary,
            output_format=output_format,
            granularity=granularity,
            bilingual=bilingual,
            voice_profile=voice_profile,
            decision_mode=decision_mode,
            narrative_style=narrative_style,
        )
        if self.chat_model_cls is None:
            return (
                "[Aviso: ChatOpenAI indisponível no ambiente]\n\n"
                "Resumo JSON:\n" + str(summary) + "\n\n"
                "Solicitação:\n" + analysis_query + "\n\n"
                "(Nesta etapa, um LLM redigiria a narrativa com base no JSON e contexto acima.)"
            )

        llm = self.chat_model_cls(**self.llm_config.analysis_chat_openai_kwargs(self.openai_api_key))
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        first = llm.invoke(messages).content
        refined = self.refine_if_generic(llm, first, summary)
        return self.postprocess_output(refined, output_format)

    def refine_if_generic(self, llm: Any, text: str, summary: Dict[str, Any]) -> str:
        has_number = bool(re.search(r"\d{2}/\d{2}|\d{4}-\d{2}-\d{2}|\b\d{2,}[.,]?\d*\b", text))
        has_date = bool(re.search(r"\b\d{1,2}/\d{1,2}\b|\b\d{4}-\d{2}-\d{2}\b", text))
        if has_number and has_date:
            return text

        refine_prompt = render_refine_prompt(text, summary)
        out = llm.invoke(
            [
                {"role": "system", "content": "Você é um editor sênior objetivo e técnico."},
                {"role": "user", "content": refine_prompt},
            ]
        ).content
        return out or text

    def postprocess_output(self, text: str, output_format: str) -> str:
        fmt = (output_format or "detalhado").strip().lower()
        cleaned = text.strip()

        if fmt == "topicos":
            lines = cleaned.splitlines()
            has_bullets = any(line.lstrip().startswith(("-", "*", "•")) for line in lines)
            if has_bullets:
                return cleaned

            sentences = re.split(r"(?<=[.!?])\s+", cleaned)
            bullets = [f"- {sentence.strip()}" for sentence in sentences if sentence.strip()]
            if len(bullets) > 10:
                bullets = bullets[:10]
            return "\n".join(bullets)

        if fmt == "resumido":
            sentences = re.split(r"(?<=[.!?])\s+", cleaned)
            if len(sentences) > 5:
                cleaned = " ".join(sentences[:5]).strip()
            return cleaned

        return cleaned
