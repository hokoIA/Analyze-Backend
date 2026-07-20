# Analyze-Backend

Camada Python responsavel por receber dados ja preparados pelo API Gateway, montar contexto analitico, gerar a narrativa com LLM e devolver a analise para quem chamou.

## Contrato entre camadas

- O endpoint e o payload de entrada nao devem ser alterados sem coordenar com o API Gateway.
- Esta camada nao busca dados nas plataformas diretamente no fluxo de analise.
- Dados externos enviados em `external_data`, como `meta_ads` e `instagram_posts`, sao apenas organizados internamente em `summary`.
- Tokens, chaves e payloads sensiveis nao devem ser gravados em prompts, testes ou logs. Dados reais de cliente so devem aparecer no debug temporario de prompts, com flag explicita e desligado apos o teste.

## Debug temporario de prompts no Render

Use apenas para auditoria pontual em producao e desligue depois do teste, porque os logs podem conter metricas, legendas de posts, contexto do cliente e trechos de documentos. Tokens, senhas e chaves sao mascarados automaticamente por chave e padrao de valor.

Variaveis:

- `ANALYZE_DEBUG_PROMPT_LOGS=true`: liga os logs detalhados do fluxo de analise.
- `ANALYZE_DEBUG_PROMPT_SUMMARY_ONLY=true`: opcional; mostra apenas formato/preview dos dados, sem despejar tudo.
- `ANALYZE_DEBUG_PROMPT_CHUNK_SIZE=12000`: opcional; tamanho dos blocos impressos no console.
- `ANALYZE_DEBUG_PROMPT_MAX_CHARS=0`: opcional; `0` deixa sem corte, outro numero limita cada evento.

Eventos principais no console:

- `analysis_request_received`: configuracao recebida da analise.
- `analysis_external_data_received`: dados enviados pelo API Gateway em `external_data`.
- `analysis_external_summary_built`: resumo gerado a partir dos dados externos.
- `analysis_db_platform_dataframe`: dados organicos carregados do banco por plataforma.
- `analysis_merged_dataframe`: dados organicos finais consolidados.
- `analysis_final_summary_sent_to_prompt`: `summary` final usado no prompt.
- `analysis_rag_query` e `analysis_rag_context_retrieved`: busca e contexto recuperado.
- `analysis_system_prompt_final` e `analysis_user_prompt_final`: prompts finais enviados ao LLM.
- `analysis_llm_first_output`, `analysis_refine_prompt_final`, `analysis_refine_output` e `analysis_llm_final_output`: resposta bruta, refinamento quando houver e resposta final.

## Onde editar prompts

Os prompts editaveis ficam em `utils/prompts/analysis`.

- `blocks/`: regras globais, estilo, persona, saida, bilingue e refinamento.
- `types/`: instrucao por tipo de analise (`descriptive`, `predictive`, `prescriptive`, `general`).
- `focus/`: vies por foco estrategico (`branding`, `negocio`, `conexao`, `panorama`).
- `platforms/`: instrucao por plataforma (`instagram`, `facebook`, `google_analytics`, `linkedin`, `meta_ads`).
- `defaults/`: perguntas padrao quando a UI nao envia uma pergunta especifica.
- `examples/`: exemplos/few-shots reutilizaveis.

Para mudar o texto da analise, prefira editar esses arquivos `.md`. Evite mexer no pipeline Python quando a mudanca for apenas copy, tom, regra de narrativa ou instrucao de prompt.

## Padrao de engenharia de prompt

O prompt de analise segue uma estrutura inspirada em: papel, tarefa, contexto, criterios de evidencia, regras complementares, saida e condicoes de qualidade.

Principios atuais:

- A resposta final deve ser baseada em dados, contexto e pedido do usuario.
- Cada insight central deve conectar evidencia observada, interpretacao e implicacao.
- Hipoteses devem ser escritas como hipoteses, sem falsa certeza causal.
- Termos tecnicos internos como API, JSON, RAG, prompt, modelo, token, banco de dados, payload e schema nao devem aparecer para o cliente final.
- Quando os dados nao sustentarem uma conclusao, a resposta deve assumir essa limitacao em linguagem simples.
- Posts, campanhas, conjuntos, anuncios e metricas organicas devem ser usados como evidencias quando estiverem presentes no `summary`.

## Arquitetura principal

- `utils/advanced_data_analyst.py`: orquestra o fluxo principal.
- `utils/dataframe/normalizer.py`: normaliza colunas e datas dos dados organicos vindos do banco.
- `utils/summary/organic_summary_builder.py`: monta o `summary` organico.
- `utils/external_data/summary_builder.py`: organiza `external_data` recebido do API Gateway, incluindo Meta Ads e posts do Instagram.
- `utils/rag/query_builder.py`: monta a query usada para buscar contexto no VectorDB.
- `utils/narrative/service.py`: monta prompts, chama o LLM, refina resposta generica e aplica pos-processamento.
- `utils/llm/config.py`: centraliza modelos e parametros de LLM.

## Configuracao de LLM

Defaults atuais:

- `ANALYZE_LLM_MODEL`: `gpt-5.4`
- `CHAT_LLM_MODEL`: `gpt-4o`
- `GOALS_LLM_MODEL`: `gpt-5.4`
- `CHAT_LLM_TEMPERATURE`: `0.3`
- `ANALYZE_LLM_PRESENCE_PENALTY`: `0.1`
- `ANALYZE_LLM_FREQUENCY_PENALTY`: `0.1`

Overrides opcionais:

- `ANALYZE_LLM_TEMPERATURE`
- `ANALYZE_LLM_MODEL`
- `CHAT_LLM_MODEL`
- `CHAT_LLM_TEMPERATURE`
- `GOALS_LLM_MODEL`

## Vistoria tecnica atual

Estado atual:

- A aplicacao usa LangChain com `ChatOpenAI` para gerar a narrativa.
- O uso atual continua valido e compativel, mas a chamada principal ainda segue o caminho de Chat Completions por meio do LangChain.
- Para evolucao futura de qualidade, a proxima investigacao tecnica deve comparar o fluxo atual com Responses API usando modelo de raciocinio, controle de `reasoning.effort` e, se fizer sentido, prompt caching para prefixos estaveis.
- Essa migracao nao deve ser feita junto com ajustes de prompt, porque muda a camada de chamada LLM e precisa de validacao propria de custo, latencia, qualidade e compatibilidade.

Checklist sugerido para uma etapa futura:

- Criar um adapter de LLM para manter `AnalysisNarrativeService` independente do provedor.
- Rodar comparativo A/B com as mesmas entradas entre ChatOpenAI atual e Responses API.
- Medir qualidade da analise, tempo de resposta, tokens e falhas.
- So entao trocar o default de producao, se houver ganho claro.

## Validacao local

Rode a suite antes de publicar alteracoes:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Testes principais:

- `tests/test_prompt_renderer.py`: renderer modular de prompts.
- `tests/test_prompt_snapshots.py`: estrutura minima dos prompts.
- `tests/test_instagram_posts_external_summary.py`: posts do Instagram recebidos via API Gateway entrando no `summary`.
- `tests/test_analysis_integration.py`: fluxo integrado com DB, VectorDB e LLM mockados.
