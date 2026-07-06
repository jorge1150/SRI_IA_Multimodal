"""
benchmark_dataset.py — Parser de preguntas.docx para scripts/run_benchmark.py.

Formato esperado del .docx (ver preguntas.docx en la raíz del proyecto):
  - Título y "N Documentos PDF" — se ignoran.
  - Categoría de normativa: párrafo en negrita (ej. "IVA (Impuesto al Valor
    Agregado)") — coincide con el nombre de carpeta en data/.
  - Nombre de documento fuente: párrafo no negrita, no numerado, distinto
    de la etiqueta fija "Preguntas de comprensión y aplicación:".
  - Preguntas: líneas "1. ..."/"2. ..." o "Pregunta 1: ..."/"Pregunta 2: ...".

No todas las secciones usan el mismo estilo Word (algunas usan "Heading 2"
para el nombre del documento, otras "Normal") — por eso el parser se basa en
negrita/contenido, no en el nombre de estilo.
"""

import re

_LABEL = "Preguntas de comprensión y aplicación:"
_TITLE_LINE_RE = re.compile(r'^Preguntas de Estudio', re.IGNORECASE)
_DOC_COUNT_RE = re.compile(r'^\d+\s+Documentos?\s+PDF', re.IGNORECASE)
_QUESTION_RE = re.compile(r'^(?:\d+\.|Pregunta\s+\d+:)\s*(.+)', re.IGNORECASE)


def _is_bold(paragraph) -> bool:
    return any(run.bold for run in paragraph.runs if run.bold)


def parse_questions_docx(path: str) -> list[dict]:
    """
    Retorna una lista de dicts: {"category": str, "source_doc": str, "question": str}.
    category/source_doc quedan como "" si aparece una pregunta antes de que
    se detecte alguno de los dos (no debería ocurrir con el formato real).
    """
    from docx import Document

    doc = Document(path)
    records: list[dict] = []
    category = ""
    source_doc = ""

    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if text == _LABEL or _TITLE_LINE_RE.match(text) or _DOC_COUNT_RE.match(text):
            continue

        m = _QUESTION_RE.match(text)
        if m:
            records.append({
                "category": category,
                "source_doc": source_doc,
                "question": m.group(1).strip(),
            })
            continue

        if _is_bold(p):
            category = text
        else:
            source_doc = text

    return records
