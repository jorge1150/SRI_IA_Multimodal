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
