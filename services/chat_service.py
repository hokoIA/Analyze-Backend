# services/chat_service.py
import os
from openai import OpenAI
from utils.db.vector_db import VectorDBManager
from utils.llm.config import get_llm_config
from utils.prompts.system_prompts import build_chat_system_prompt


class ChatService:
    def __init__(self):
        self.vector_db_manager = VectorDBManager(
            pinecone_api_key=os.getenv("PINECONE_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.llm_config = get_llm_config()

    def generate_chat_response(self, customer_id: int, client_name: str, client_id: int, prompt: str, history: list):
        vectordb = self.vector_db_manager.create_or_load_vector_db(str(customer_id), str(client_id))

        retriever = vectordb.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 10}
        )

        context_docs = retriever.invoke(prompt)
        context_text = "\n\n".join([doc.page_content for doc in context_docs])

        openai_messages = []

        system_message = build_chat_system_prompt(
            client_name=client_name,
            voice_profile=os.getenv("CHAT_VOICE_PROFILE","CMO"),
            analysis_focus=os.getenv("CHAT_ANALYSIS_FOCUS", "panorama")  # ou parâmetro
        )
        
        openai_messages.append({"role": "system", "content": system_message})

        # Limita o histórico às últimas 8 mensagens
        for msg in history[-8:]:
            openai_messages.append({"role": msg["role"], "content": msg["content"]})

        openai_messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.llm_config.chat_model,
            messages=openai_messages,
            temperature=self.llm_config.chat_temperature
        )

        return response.choices[0].message.content
