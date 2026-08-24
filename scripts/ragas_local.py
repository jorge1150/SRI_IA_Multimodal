"""
ragas_local.py — Juez y embeddings 100% locales para RAGAS.

RAGAS por defecto usa OpenAI como juez y para embeddings — este proyecto es
100% local (ver CONTEXT.md), así que ambos se reemplazan:
  - Juez: el mismo Ollama del proyecto (LangchainLLMWrapper sobre ChatOllama).
  - Embeddings: sentence-transformers multilingüe (no OpenCLIP — CLIP está
    optimizado para alinear imagen-texto, no para comparar dos textos entre
    sí; usarlo daría métricas de similitud ruidosas, ver grilling de la
    candidata de benchmark).

Limitación conocida y aceptada: un juez de 3B es menos confiable evaluando
que GPT-4 — los scores de faithfulness/answer_relevancy sirven para comparar
modos/modelos entre sí (todos evaluados por el mismo juez), no como medida
absoluta de calidad.
"""

from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.run_config import RunConfig

DEFAULT_JUDGE_MODEL = "qwen2.5:3b-instruct-q4_K_M"
DEFAULT_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def make_judge_llm(model: str = DEFAULT_JUDGE_MODEL, ollama_url: str = "http://localhost:11434"):
    from langchain_ollama import ChatOllama
    from ragas.llms import LangchainLLMWrapper
    return LangchainLLMWrapper(ChatOllama(model=model, base_url=ollama_url, temperature=0.0))


def is_claude_model(model: str) -> bool:
    """Nombres de modelo Claude ('claude-opus-5', 'claude-sonnet-5', ...) van
    por la API de Anthropic (ANTHROPIC_API_KEY), no por Ollama — ver
    make_claude_judge_llm."""
    return model.startswith("claude-")


def make_claude_judge_llm(model: str = "claude-sonnet-5"):
    """Juez RAGAS vía API de Anthropic en vez de Ollama Cloud (2026-08-24).
    Motivación: la cuota gratis de Ollama Cloud + un juez "thinking" lento
    hacía que el juzgamiento completo (800 filas × 5 métricas) tomara días
    repartido en varias sesiones (ver ADR-0016). Claude, además de no tener
    techo de cuota semanal (es pago por token, prepago — ver CONTEXT.md),
    sigue formato estructurado de forma mucho más confiable que un juez
    abierto chico, lo que además debería subir la cobertura RAGAS (menos
    filas sin parsear), no solo la velocidad.

    Requiere `pip install langchain-anthropic` y `ANTHROPIC_API_KEY` en el
    entorno (no es lo mismo que una suscripción Claude Pro — hace falta una
    cuenta de API separada en console.anthropic.com).

    Ojo self-preference bias (ADR-0016): no usar el mismo modelo como juez
    y como uno de los modelos comparados en --models. Acá no aplica porque
    los modelos comparados (gemma4:31b-cloud, gpt-oss:20b-cloud) son ambos
    de Ollama Cloud, distintos de la familia Claude.

    NO pasar temperature: en Claude Sonnet 5 / Opus 5 (thinking adaptativo
    por defecto) el parámetro de sampling explícito devuelve
    400 `temperature is deprecated for this model` — confirmado en vivo
    (2026-08-24). Determinismo del juez queda a cargo del default del
    modelo, no de temperature=0.

    max_tokens=4096 explícito: el default del wrapper se quedaba corto con
    claude-haiku-4-5 en answer_correctness (LLMDidNotFinishException,
    0/2 parseadas en prueba real) — la respuesta se cortaba a mitad de la
    salida estructurada que RAGAS exige."""
    from langchain_anthropic import ChatAnthropic
    from ragas.llms import LangchainLLMWrapper
    return LangchainLLMWrapper(ChatAnthropic(model=model, max_tokens=4096))


class LocalTextEmbeddings(BaseRagasEmbeddings):
    """
    sentence-transformers envuelto en la interfaz async que RAGAS exige.
    No se usa langchain-huggingface a propósito — esa dependencia arrastra
    una versión de langchain-core incompatible con el resto del proyecto.
    """

    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL):
        super().__init__()
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(model_name)
        self.set_run_config(RunConfig())

    def embed_query(self, text: str) -> list:
        return self._model.encode([text], normalize_embeddings=True)[0].tolist()

    def embed_documents(self, texts: list) -> list:
        return self._model.encode(list(texts), normalize_embeddings=True).tolist()

    async def aembed_query(self, text: str) -> list:
        return self.embed_query(text)

    async def aembed_documents(self, texts: list) -> list:
        return self.embed_documents(texts)


def make_embeddings(model_name: str = DEFAULT_EMBEDDING_MODEL) -> LocalTextEmbeddings:
    return LocalTextEmbeddings(model_name)
