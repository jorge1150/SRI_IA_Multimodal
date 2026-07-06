"""
ingesta.py — Ingesta de documentos normativos SRI a ChromaDB.
Procesa PDF, TXT, DOCX y MD desde las carpetas de datos,
vectoriza con OpenCLIP y almacena con metadatos completos.
"""

import os
import glob
import json
import time
import torch
import open_clip
import chromadb

from config import (
    CLIP_MODEL, CLIP_PRETRAINED, CLIP_MAX_TOKENS,
    CHROMA_DB_PATH, CHROMA_COLLECTION, VECTOR_BUILD_METADATA_PATH,
    get_data_dirs,
)
from .chunker import chunk_document

SUPPORTED_EXTENSIONS = ("*.pdf", "*.txt", "*.docx", "*.md")


def _load_build_seconds() -> float:
    try:
        with open(VECTOR_BUILD_METADATA_PATH, encoding="utf-8") as f:
            return json.load(f).get("build_seconds", 0.0)
    except Exception:
        return 0.0


def _save_build_metadata(build_seconds: float, last_run_seconds: float) -> None:
    from datetime import datetime
    os.makedirs(os.path.dirname(VECTOR_BUILD_METADATA_PATH), exist_ok=True)
    with open(VECTOR_BUILD_METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "build_seconds": build_seconds,
            "last_run_seconds": last_run_seconds,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }, f, ensure_ascii=False, indent=2)


def get_clip_embedder():
    print(f"[INGESTA] Cargando OpenCLIP {CLIP_MODEL} en CPU...")
    clip_device = "cpu"
    kwargs = {} if CLIP_MODEL.startswith("hf-hub:") else {"pretrained": CLIP_PRETRAINED}
    model, _, _ = open_clip.create_model_and_transforms(CLIP_MODEL, **kwargs)
    model = model.to(clip_device).eval()
    tokenizer = open_clip.get_tokenizer(CLIP_MODEL)
    return model, tokenizer, clip_device


def embed_text(text: str, model, tokenizer, device: str) -> list[float]:
    tokens = tokenizer([text[:CLIP_MAX_TOKENS]]).to(device)
    with torch.no_grad():
        vec = model.encode_text(tokens)
        vec /= vec.norm(dim=-1, keepdim=True)
    return vec.cpu().numpy().flatten().tolist()


def ingest_all_documents(reset: bool = False) -> int:
    """
    Ingesta todos los documentos SRI de las carpetas de datos a ChromaDB.
    Soporta: PDF, TXT, DOCX, MD.
    Guarda metadatos ricos: doc_name, tipo_normativa, año, pagina,
    articulo_seccion, ruta_archivo, source.

    reset=True borra la colección antes de ingestar.
    Retorna el número de chunks insertados.
    """
    t0 = time.time()
    accumulated_seconds = 0.0 if reset else _load_build_seconds()

    # ── Recopilar todos los documentos ──────────────────────────────────────
    data_dirs = get_data_dirs()
    all_files: list[tuple[str, str]] = []  # (filepath, tipo_normativa)
    for data_dir in data_dirs:
        tipo = os.path.basename(data_dir)
        for ext in SUPPORTED_EXTENSIONS:
            for fp in glob.glob(os.path.join(data_dir, ext)):
                all_files.append((fp, tipo))

    if not all_files:
        print("[INGESTA] No se encontraron documentos SRI en las carpetas de datos.")
        print("  Copia tus documentos en una subcarpeta de data/ — el nombre de")
        print("  la carpeta se usa como tipo de normativa (ej. data/IVA/...).")
        return 0

    print(f"[INGESTA] {len(all_files)} documento(s) encontrado(s).")

    # ── Conectar a ChromaDB ──────────────────────────────────────────────────
    os.makedirs(CHROMA_DB_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    if reset:
        try:
            client.delete_collection(CHROMA_COLLECTION)
            print(f"[INGESTA] Colección '{CHROMA_COLLECTION}' eliminada.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    # ── Cargar modelo de embeddings ──────────────────────────────────────────
    model, tokenizer, clip_device = get_clip_embedder()

    # ── IDs existentes (modo incremental) ───────────────────────────────────
    existing_ids: set = set()
    if not reset:
        existing_ids = set(collection.get()["ids"])

    # ── Procesar cada documento ──────────────────────────────────────────────
    total_chunks = 0
    for filepath, tipo_normativa in all_files:
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        print(f"[INGESTA] Procesando [{tipo_normativa}]: {filename}", flush=True)

        chunks = chunk_document(filepath, tipo_normativa=tipo_normativa)
        new_chunks = [c for c in chunks if c["id"] not in existing_ids]
        print(f"           → {len(chunks)} fragmentos ({len(new_chunks)} nuevos)", flush=True)

        if not new_chunks:
            print("           ✓ Sin cambios.", flush=True)
            continue

        # Vectorizar y preparar batch
        ids_batch, docs_batch, metas_batch, vecs_batch = [], [], [], []
        for chunk in new_chunks:
            # Tabla/ecuación: graph_text (caption+footnote, sin HTML/LaTeX) es lo
            # que se embebe — chunk["text"] completo se sigue mostrando al LLM
            # (docs_batch abajo), solo el vector cambia (ADR-0004).
            texto_para_embed = chunk["graph_text"] or chunk["text"]
            vec = embed_text(texto_para_embed, model, tokenizer, clip_device)
            ids_batch.append(chunk["id"])
            docs_batch.append(chunk["text"])
            metas_batch.append({
                "source":           chunk["source"],
                "doc_name":         str(chunk.get("doc_name", "")),
                "tipo_normativa":   str(chunk.get("tipo_normativa", "")),
                "año":              str(chunk.get("año", "")),
                "pagina":           str(chunk.get("pagina", "")),
                "articulo_seccion": str(chunk.get("articulo_seccion", "")),
                "ruta_archivo":     str(chunk.get("ruta_archivo", "")),
            })
            vecs_batch.append(vec)

        # Upsert batch por documento
        collection.upsert(
            embeddings=vecs_batch,
            documents=docs_batch,
            metadatas=metas_batch,
            ids=ids_batch,
        )
        total_chunks += len(ids_batch)
        print(f"           ✓ {len(ids_batch)} fragmentos insertados.", flush=True)

    print(f"\n[INGESTA] Total fragmentos en ChromaDB: {collection.count()}", flush=True)

    elapsed = time.time() - t0
    _save_build_metadata(build_seconds=accumulated_seconds + elapsed, last_run_seconds=elapsed)

    return total_chunks
