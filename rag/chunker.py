"""
chunker.py — Fragmentación de documentos normativos SRI.
Soporta: PDF (con número de página), DOCX, TXT y MD.
Cada chunk incluye metadatos ricos para citar la fuente correctamente.
"""

import os
import re
from typing import List


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 60) -> List[str]:
    """
    Divide texto en fragmentos con overlap.
    Corta en el último punto o espacio para no romper oraciones.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # Intentar cortar en punto final o espacio
            cut = text.rfind(". ", start, end)
            if cut > start + chunk_size // 2:
                end = cut + 1
            else:
                last_space = text.rfind(" ", start, end)
                if last_space > start:
                    end = last_space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _extract_articulo(text: str) -> str:
    """Detecta referencia a artículo o sección en el texto."""
    patterns = [
        r'Art\.\s*\d+[\w\.\-]*',
        r'Artículo\s+\d+[\w\.\-]*',
        r'Sección\s+\d+[\w\.\-]*',
        r'Capítulo\s+[IVXLC\d]+',
        r'Disposición\s+\w+\s+\w+',
        r'Numeral\s+\d+',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(0)
    return ""


def _extract_year(filename: str) -> str:
    """Extrae año del nombre del archivo."""
    m = re.search(r'(20\d{2}|19\d{2})', filename)
    return m.group(1) if m else ""


def chunk_txt(filepath: str, chunk_size: int = 500, overlap: int = 60,
              tipo_normativa: str = "", doc_name_override: str = "") -> List[dict]:
    """Fragmenta archivo TXT con metadatos."""
    filename = os.path.basename(filepath)
    name_no_ext = os.path.splitext(filename)[0]
    doc_name = doc_name_override or name_no_ext.replace("_", " ").title()
    año = _extract_year(filename)

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    raw_chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
    result = []
    for i, chunk in enumerate(raw_chunks):
        art = _extract_articulo(chunk)
        result.append({
            "id": f"{name_no_ext}_{i:04d}",
            "text": chunk,
            "source": filename,
            "doc_name": doc_name,
            "tipo_normativa": tipo_normativa,
            "año": año,
            "pagina": "",
            "articulo_seccion": art,
            "ruta_archivo": filepath,
        })
    return result


def chunk_md(filepath: str, chunk_size: int = 500, overlap: int = 60,
             tipo_normativa: str = "", doc_name_override: str = "") -> List[dict]:
    """Fragmenta archivo Markdown — igual que TXT, preserva texto."""
    return chunk_txt(filepath, chunk_size=chunk_size, overlap=overlap,
                     tipo_normativa=tipo_normativa, doc_name_override=doc_name_override)


def chunk_docx(filepath: str, chunk_size: int = 500, overlap: int = 60,
               tipo_normativa: str = "", doc_name_override: str = "") -> List[dict]:
    """Fragmenta archivo DOCX extrayendo párrafos."""
    try:
        from docx import Document
    except ImportError:
        print("[CHUNKER] python-docx no instalado. Instala: pip install python-docx")
        return []

    filename = os.path.basename(filepath)
    name_no_ext = os.path.splitext(filename)[0]
    doc_name = doc_name_override or name_no_ext.replace("_", " ").title()
    año = _extract_year(filename)

    doc = Document(filepath)
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    raw_chunks = chunk_text(full_text, chunk_size=chunk_size, overlap=overlap)
    result = []
    for i, chunk in enumerate(raw_chunks):
        art = _extract_articulo(chunk)
        result.append({
            "id": f"{name_no_ext}_{i:04d}",
            "text": chunk,
            "source": filename,
            "doc_name": doc_name,
            "tipo_normativa": tipo_normativa,
            "año": año,
            "pagina": "",
            "articulo_seccion": art,
            "ruta_archivo": filepath,
        })
    return result


def chunk_pdf(filepath: str, chunk_size: int = 500, overlap: int = 60,
              tipo_normativa: str = "", doc_name_override: str = "") -> List[dict]:
    """
    Fragmenta PDF página por página con PyMuPDF.
    Cada chunk incluye el número de página de origen.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("[CHUNKER] PyMuPDF no instalado. Instala: pip install pymupdf")
        return []

    filename = os.path.basename(filepath)
    name_no_ext = os.path.splitext(filename)[0]
    doc_name = doc_name_override or name_no_ext.replace("_", " ").title()
    año = _extract_year(filename)

    result = []
    try:
        doc = fitz.open(filepath)
        # Intentar obtener título de los metadatos del PDF
        pdf_meta = doc.metadata
        if pdf_meta.get("title") and len(pdf_meta["title"]) > 3:
            doc_name = pdf_meta["title"].strip()
        if not año and pdf_meta.get("creationDate"):
            m = re.search(r'(20\d{2}|19\d{2})', pdf_meta["creationDate"])
            if m:
                año = m.group(1)

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if not text.strip():
                continue

            page_chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
            for i, chunk in enumerate(page_chunks):
                art = _extract_articulo(chunk)
                chunk_id = f"{name_no_ext}_p{page_num+1:03d}_{i:04d}"
                result.append({
                    "id": chunk_id,
                    "text": chunk,
                    "source": filename,
                    "doc_name": doc_name,
                    "tipo_normativa": tipo_normativa,
                    "año": año,
                    "pagina": page_num + 1,
                    "articulo_seccion": art,
                    "ruta_archivo": filepath,
                })
        doc.close()
    except Exception as exc:
        print(f"[CHUNKER] Error procesando PDF {filepath}: {exc}")

    return result


def chunk_document(
    filepath: str,
    chunk_size: int = 500,
    overlap: int = 60,
    tipo_normativa: str = "",
    doc_name_override: str = "",
) -> List[dict]:
    """
    Detecta el tipo de archivo y fragmenta con el método correcto.
    Retorna lista de dicts con: id, text, source, doc_name, tipo_normativa,
    año, pagina, articulo_seccion, ruta_archivo.
    """
    ext = os.path.splitext(filepath)[1].lower()
    kwargs = dict(
        chunk_size=chunk_size,
        overlap=overlap,
        tipo_normativa=tipo_normativa,
        doc_name_override=doc_name_override,
    )
    if ext == ".pdf":
        return chunk_pdf(filepath, **kwargs)
    elif ext == ".docx":
        return chunk_docx(filepath, **kwargs)
    elif ext == ".md":
        return chunk_md(filepath, **kwargs)
    else:
        return chunk_txt(filepath, **kwargs)
