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
            # Intentar cortar en punto final (solo si avanza suficiente)
            cut = text.rfind(". ", start, end)
            if cut > start + chunk_size // 2:
                end = cut + 1
            else:
                # Solo usar espacio si garantiza avance real (> overlap)
                last_space = text.rfind(" ", start + overlap, end)
                if last_space > start + overlap:
                    end = last_space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        new_start = end - overlap
        # Garantizar siempre avance — evita loop infinito
        start = new_start if new_start > start else end
    return chunks


def _extract_articulo(text: str) -> str:
    """Detecta referencia a artículo o sección en el texto."""
    # Sufijo de subdivisión: permite "65-A", "10.2", pero exige carácter de
    # palabra después de la puntuación — la clase antigua [\w\.\-]* capturaba
    # la puntuación colgante de encabezados ("Art. 65.- Tarifa" → "Art. 65.-").
    patterns = [
        r'Art\.\s*\d+(?:[.\-]\w+)*',
        r'Artículo\s+\d+(?:[.\-]\w+)*',
        r'Sección\s+\d+(?:[.\-]\w+)*',
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


def _derive_doc_identity(filepath: str, doc_name_override: str = "") -> tuple:
    """Deriva (filename, name_no_ext, doc_name, año) a partir de la ruta del archivo."""
    filename = os.path.basename(filepath)
    name_no_ext = os.path.splitext(filename)[0]
    doc_name = doc_name_override or name_no_ext.replace("_", " ").title()
    año = _extract_year(filename)
    return filename, name_no_ext, doc_name, año


def make_chunk(*, id: str, text: str, source: str, doc_name: str, tipo_normativa: str,
               año: str, pagina, articulo_seccion: str, ruta_archivo: str,
               kind: str = "paragraph", graph_text: str = "") -> dict:
    """
    Constructor único del dict de chunk. kind y graph_text siempre presentes
    (aunque vacío/"paragraph" por defecto) — un esquema, no uno distinto por
    productor (candidata C, arquitectura RAG).
    """
    return {
        "id": id,
        "text": text,
        "source": source,
        "doc_name": doc_name,
        "tipo_normativa": tipo_normativa,
        "año": año,
        "pagina": pagina,
        "articulo_seccion": articulo_seccion,
        "ruta_archivo": ruta_archivo,
        "kind": kind,
        "graph_text": graph_text,
    }


def chunk_txt(filepath: str, chunk_size: int = 500, overlap: int = 60,
              tipo_normativa: str = "", doc_name_override: str = "") -> List[dict]:
    """Fragmenta archivo TXT con metadatos."""
    filename, name_no_ext, doc_name, año = _derive_doc_identity(filepath, doc_name_override)

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    raw_chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
    result = []
    for i, chunk in enumerate(raw_chunks):
        result.append(make_chunk(
            id=f"{name_no_ext}_{i:04d}", text=chunk, source=filename, doc_name=doc_name,
            tipo_normativa=tipo_normativa, año=año, pagina="",
            articulo_seccion=_extract_articulo(chunk), ruta_archivo=filepath,
        ))
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

    filename, name_no_ext, doc_name, año = _derive_doc_identity(filepath, doc_name_override)

    doc = Document(filepath)
    full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    raw_chunks = chunk_text(full_text, chunk_size=chunk_size, overlap=overlap)
    result = []
    for i, chunk in enumerate(raw_chunks):
        result.append(make_chunk(
            id=f"{name_no_ext}_{i:04d}", text=chunk, source=filename, doc_name=doc_name,
            tipo_normativa=tipo_normativa, año=año, pagina="",
            articulo_seccion=_extract_articulo(chunk), ruta_archivo=filepath,
        ))
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

    filename, name_no_ext, doc_name, año = _derive_doc_identity(filepath, doc_name_override)

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
                result.append(make_chunk(
                    id=f"{name_no_ext}_p{page_num+1:03d}_{i:04d}", text=chunk,
                    source=filename, doc_name=doc_name, tipo_normativa=tipo_normativa,
                    año=año, pagina=page_num + 1,
                    articulo_seccion=_extract_articulo(chunk), ruta_archivo=filepath,
                ))
        doc.close()
    except Exception as exc:
        print(f"[CHUNKER] Error procesando PDF {filepath}: {exc}")

    return result


def chunk_pdf_mineru(filepath: str, chunk_size: int = 500, overlap: int = 60,
                      tipo_normativa: str = "", doc_name_override: str = "") -> List[dict]:
    """
    Fragmenta PDF con MinerU (https://github.com/opendatalab/MinerU).
    A diferencia de chunk_pdf (PyMuPDF), reconoce layout, tablas (HTML),
    fórmulas (LaTeX) y aplica OCR — útil para normativa escaneada o con
    tablas de tarifas. Cada bloque conserva su página de origen (page_idx).

    Cada heading (bloque "text" con "text_level") abre una nueva sección:
    ningún chunk de prosa cruza dos secciones, y articulo_seccion se recalcula
    contra el texto del heading (no contra prosa aplanada). Un cambio de
    página también corta, aunque la sección siga — pagina siempre es exacta.
    Tablas y fórmulas quedan como chunks propios (kind="table"/"equation"),
    heredan el articulo_seccion vigente, y llevan un graph_text (caption +
    footnote, sin HTML/LaTeX) separado del text de display para que el
    knowledge graph no reciba HTML/LaTeX crudo.

    MinerU vive en su propio venv (venv_mineru/, ver config.MINERU_BIN)
    porque fuerza numpy>=2, incompatible con torch==2.2.2 del venv principal.
    Si el binario no existe o falla, quien llame debe hacer fallback a chunk_pdf.
    """
    import json
    import subprocess
    import tempfile

    from config import MINERU_BACKEND, MINERU_BIN, MINERU_DEVICE, MINERU_TIMEOUT

    if not os.path.isfile(MINERU_BIN):
        raise RuntimeError(
            f"MinerU no instalado en {MINERU_BIN}. Instala con: "
            f"python3.12 -m venv venv_mineru && "
            f"venv_mineru/bin/pip install \"mineru[pipeline]\""
        )

    filename, name_no_ext, doc_name, año = _derive_doc_identity(filepath, doc_name_override)

    with tempfile.TemporaryDirectory() as out_dir:
        subprocess.run(
            [MINERU_BIN, "-p", filepath, "-o", out_dir,
             "-b", MINERU_BACKEND, "-d", MINERU_DEVICE],
            check=True,
            capture_output=True,
            timeout=MINERU_TIMEOUT,
        )

        content_list_path = None
        for root, _, files in os.walk(out_dir):
            for f in files:
                if f.endswith("_content_list.json"):
                    content_list_path = os.path.join(root, f)
                    break
            if content_list_path:
                break

        if not content_list_path:
            raise RuntimeError(f"MinerU no generó content_list.json para {filename}")

        with open(content_list_path, "r", encoding="utf-8") as f:
            blocks = json.load(f)

    result = _chunks_from_mineru_blocks(
        blocks, name_no_ext=name_no_ext, filename=filename, doc_name=doc_name,
        tipo_normativa=tipo_normativa, año=año, filepath=filepath,
        chunk_size=chunk_size, overlap=overlap,
    )
    return result


def _chunks_from_mineru_blocks(blocks: List[dict], *, name_no_ext: str, filename: str,
                                doc_name: str, tipo_normativa: str, año: str,
                                filepath: str, chunk_size: int, overlap: int) -> List[dict]:
    """
    Agrupa bloques de content_list.json de MinerU en secciones (runs) y chunks
    especiales (tabla/ecuación). Separado de chunk_pdf_mineru para poder
    testear el agrupamiento con fixtures sintéticas, sin invocar el binario.
    """
    SKIP_TYPES = {"page_number", "footer", "header"}
    runs: List[dict] = []       # {"page_idx", "articulo_seccion", "texts": [...]}
    special_chunks: List[dict] = []  # tabla/ecuación, en orden de aparición
    current_articulo = ""
    active_run = None

    def start_run(page_idx: int) -> dict:
        run = {"page_idx": page_idx, "articulo_seccion": current_articulo, "texts": []}
        runs.append(run)
        return run

    for block in blocks:
        btype = block.get("type", "text")
        page_idx = block.get("page_idx", 0)
        if btype in SKIP_TYPES:
            continue

        if btype == "table":
            table_html = block.get("table_body", "") or block.get("content", "")
            caption = " ".join(block.get("table_caption", []) or [])
            footnote = " ".join(block.get("table_footnote", []) or [])
            display = "\n".join(p for p in (caption, table_html, footnote) if p).strip()
            graph_text = " ".join(p for p in (caption, footnote) if p).strip()
            if display:
                special_chunks.append({
                    "page_idx": page_idx, "kind": "table",
                    "text": display, "graph_text": graph_text,
                    "articulo_seccion": current_articulo,
                })
            continue

        if btype == "equation":
            eq_text = block.get("text", "").strip()
            if eq_text:
                special_chunks.append({
                    "page_idx": page_idx, "kind": "equation",
                    "text": eq_text, "graph_text": "",
                    "articulo_seccion": current_articulo,
                })
            continue

        if btype == "image":
            text = " ".join(block.get("image_caption", []) or [])
            text_level = None
            if not text:
                continue
        else:
            text = block.get("text", "").strip()
            text_level = block.get("text_level")
            if not text:
                continue

        if text_level:
            current_articulo = _extract_articulo(text)
            active_run = start_run(page_idx)
            active_run["texts"].append(text)
            continue

        if active_run is None or active_run["page_idx"] != page_idx:
            active_run = start_run(page_idx)
        active_run["texts"].append(text)

    result = []
    counter = 0
    for run in runs:
        full_text = "\n".join(run["texts"]).strip()
        if not full_text:
            continue
        for chunk in chunk_text(full_text, chunk_size=chunk_size, overlap=overlap):
            result.append(make_chunk(
                id=f"{name_no_ext}_p{run['page_idx']+1:03d}_{counter:04d}", text=chunk,
                source=filename, doc_name=doc_name, tipo_normativa=tipo_normativa, año=año,
                pagina=run["page_idx"] + 1, articulo_seccion=run["articulo_seccion"],
                ruta_archivo=filepath, kind="paragraph",
            ))
            counter += 1

    for j, sc in enumerate(special_chunks):
        prefix = "tbl" if sc["kind"] == "table" else "eqn"
        result.append(make_chunk(
            id=f"{name_no_ext}_{prefix}{sc['page_idx']+1:03d}_{j:04d}", text=sc["text"],
            source=filename, doc_name=doc_name, tipo_normativa=tipo_normativa, año=año,
            pagina=sc["page_idx"] + 1, articulo_seccion=sc["articulo_seccion"],
            ruta_archivo=filepath, kind=sc["kind"], graph_text=sc["graph_text"],
        ))

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
    año, pagina, articulo_seccion, ruta_archivo. Los chunks de chunk_pdf_mineru
    agregan además "kind" ("paragraph"/"table"/"equation"); tabla y ecuación
    agregan "graph_text" (texto plano seguro para el knowledge graph).
    """
    ext = os.path.splitext(filepath)[1].lower()
    kwargs = dict(
        chunk_size=chunk_size,
        overlap=overlap,
        tipo_normativa=tipo_normativa,
        doc_name_override=doc_name_override,
    )
    if ext == ".pdf":
        from config import USE_MINERU_PDF
        if USE_MINERU_PDF:
            try:
                return chunk_pdf_mineru(filepath, **kwargs)
            except Exception as exc:
                print(f"[CHUNKER] MinerU falló en {os.path.basename(filepath)} "
                      f"({exc}), usando PyMuPDF como fallback.")
        return chunk_pdf(filepath, **kwargs)
    elif ext == ".docx":
        return chunk_docx(filepath, **kwargs)
    elif ext == ".md":
        return chunk_md(filepath, **kwargs)
    else:
        return chunk_txt(filepath, **kwargs)
