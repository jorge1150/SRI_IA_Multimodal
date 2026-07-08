"""
rag_agent.py — Agente RAG para Normativa Tributaria SRI Ecuador
Vectoriza la consulta con OpenCLIP y recupera fragmentos normativos
relevantes desde ChromaDB, incluyendo metadatos de fuente completos.
"""

import re
import torch
import open_clip
import chromadb
from typing import List

from config import (
    DEVICE, CLIP_MODEL, CLIP_PRETRAINED, CLIP_MAX_TOKENS,
    CHROMA_DB_PATH, CHROMA_COLLECTION,
    RAG_TOP_K, RAG_MIN_SIMILARITY,
)
from .log_agent import LogAgent, Stage

# Stopwords del dominio tributario — no aportan señal de búsqueda
_STOPWORDS_SRI = {
    'para', 'como', 'cuando', 'pero', 'esto', 'esta', 'este', 'que',
    'del', 'los', 'las', 'una', 'unos', 'unas', 'por', 'con', 'sin',
    'sobre', 'entre', 'bajo', 'hace', 'tiene', 'tengo', 'puede',
    'puedo', 'creo', 'bien', 'mal', 'muy', 'hay', 'ser', 'está',
    # Genéricas del dominio tributario que aparecen en casi todos los docs
    'contribuyente', 'sri', 'ecuador', 'servicio', 'rentas', 'internas',
    'artículo', 'articulo', 'según', 'segun', 'numeral', 'literal',
    'siguiente', 'siguiente', 'dicho', 'dichos', 'caso', 'casos',
    'forma', 'manera', 'establece', 'establece', 'dispone',
}


class RAGAgent:
    """
    Motor de recuperación semántica para normativa tributaria.
    - OpenCLIP ViT-B-32 vectoriza las consultas.
    - ChromaDB almacena fragmentos de leyes, resoluciones y guías del SRI.
    - Keyword re-ranking potencia la precisión sobre texto legal.
    - Retorna metadatos completos (documento, tipo, año, artículo, página).
    """

    def __init__(self, log_agent: LogAgent):
        self.log = log_agent
        self._clip_model = None
        self._tokenizer = None
        self._preprocessor = None
        self._collection = None
        self._clip_device = "cpu"

    # ── Carga lazy ───────────────────────────────────────────────────────────

    def _load_clip(self):
        if self._clip_model is not None:
            return
        self.log.log(Stage.RAG, f"Cargando OpenCLIP {CLIP_MODEL} en CPU...")
        kwargs = {} if CLIP_MODEL.startswith("hf-hub:") else {"pretrained": CLIP_PRETRAINED}
        self._clip_model, _, self._preprocessor = open_clip.create_model_and_transforms(
            CLIP_MODEL, **kwargs
        )
        self._clip_model = self._clip_model.to(self._clip_device).eval()
        self._tokenizer = open_clip.get_tokenizer(CLIP_MODEL)
        self.log.log(Stage.RAG, "OpenCLIP listo.")

    def _load_chroma(self):
        if self._collection is not None:
            return
        self.log.log(Stage.RAG, f"Conectando a ChromaDB: {CHROMA_DB_PATH}...")
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        try:
            self._collection = client.get_collection(name=CHROMA_COLLECTION)
            count = self._collection.count()
            self.log.log(Stage.RAG, f"Colección '{CHROMA_COLLECTION}': {count} fragmentos normativos.")
        except Exception:
            self.log.log(Stage.ERROR, (
                f"Colección '{CHROMA_COLLECTION}' no existe. "
                "Carga documentos SRI y ejecuta: python rag/build_db.py"
            ))
            self._collection = None

    # ── API pública ──────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = RAG_TOP_K) -> list[dict]:
        """
        Recupera los fragmentos normativos más relevantes para la consulta.
        Retorna lista de dicts con: text, similarity, id, metadata.
        metadata contiene: doc_name, tipo_normativa, año, pagina,
                           articulo_seccion, ruta_archivo, source.
        """
        self._load_clip()
        self._load_chroma()

        if self._collection is None:
            return []

        query_vector = self._embed_text(query)
        if query_vector is None:
            return []

        candidate_k = self._collection.count()
        if candidate_k == 0:
            self.log.log(Stage.RAG, "Base vectorial vacía. Carga documentos SRI primero.")
            return []

        self.log.log(Stage.NORMATIVA, f"Buscando normativa relacionada con: «{query[:80]}»...")

        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=candidate_k,
            include=["documents", "distances", "metadatas"],
        )

        chunks = []
        docs = results.get("documents", [[]])[0]
        dists = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        for doc, dist, doc_id, meta in zip(docs, dists, ids, metas):
            similarity = 1.0 - dist
            if similarity >= RAG_MIN_SIMILARITY:
                chunks.append({
                    "text": doc,
                    "similarity": round(similarity, 3),
                    "id": doc_id,
                    "metadata": meta or {},
                })

        chunks = self._keyword_rerank(query, chunks)
        chunks = chunks[:top_k]

        if chunks:
            self.log.log(Stage.NORMATIVA, f"✓ {len(chunks)} artículo(s)/fragmento(s) recuperado(s).")
            for c in chunks:
                meta = c.get("metadata", {})
                doc_name = meta.get("doc_name", meta.get("source", "—"))
                pag = f" | Pág. {meta['pagina']}" if meta.get("pagina") else ""
                art = f" | {meta['articulo_seccion']}" if meta.get("articulo_seccion") else ""
                self.log.log(Stage.NORMATIVA, f"  [{c['id']}] sim={c['similarity']:.2f} — {doc_name}{art}{pag}")
        else:
            self.log.log(Stage.NORMATIVA, "⚠ Sin normativa relevante encontrada en la base vectorial.")

        return chunks

    # ── Re-ranking ───────────────────────────────────────────────────────────

    def _keyword_rerank(self, query: str, chunks: list[dict]) -> list[dict]:
        """
        Re-rankea por solapamiento de palabras clave tributarias con la consulta.
        Bonifica si la palabra aparece en el texto o en el ID del documento.
        """
        query_words = {
            w.lower().strip('.,;:!?¡¿()')
            for w in query.split()
            if len(w) > 2 and w.lower() not in _STOPWORDS_SRI
        }
        if not query_words:
            return chunks

        for chunk in chunks:
            text_lower = chunk["text"].lower()
            id_tokens = set(re.split(r'[_\d]+', chunk["id"].lower())) - {''}
            meta = chunk.get("metadata", {})
            doc_name_lower = (meta.get("doc_name", "") + " " + meta.get("tipo_normativa", "")).lower()

            text_hits = sum(1 for w in query_words if w in text_lower)
            source_hits = sum(1 for w in query_words if w in id_tokens)
            meta_hits = sum(1 for w in query_words if w in doc_name_lower)

            boost = 1.0 + 0.10 * text_hits + 0.25 * source_hits + 0.15 * meta_hits
            chunk["similarity"] = round(chunk["similarity"] * boost, 3)

        return sorted(chunks, key=lambda x: x["similarity"], reverse=True)

    # ── Embeddings ───────────────────────────────────────────────────────────

    def _embed_text(self, text: str) -> list[float] | None:
        try:
            tokens = self._tokenizer([text[:CLIP_MAX_TOKENS]]).to(self._clip_device)
            with torch.no_grad():
                vec = self._clip_model.encode_text(tokens)
                vec /= vec.norm(dim=-1, keepdim=True)
            return vec.cpu().numpy().flatten().tolist()
        except Exception as exc:
            self.log.log(Stage.ERROR, f"Error vectorizando texto: {exc}")
            return None

    def embed_image(self, pil_image) -> list[float] | None:
        """Vectoriza imagen PIL para búsqueda visual en ChromaDB."""
        self._load_clip()
        try:
            tensor = self._preprocessor(pil_image).unsqueeze(0).to(self._clip_device)
            with torch.no_grad():
                vec = self._clip_model.encode_image(tensor)
                vec /= vec.norm(dim=-1, keepdim=True)
            return vec.cpu().numpy().flatten().tolist()
        except Exception as exc:
            self.log.log(Stage.ERROR, f"Error vectorizando imagen: {exc}")
            return None
