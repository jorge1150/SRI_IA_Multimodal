# Embeddings de chunks-tabla usan un caption/resumen, no el HTML completo

`chunk_pdf_mineru` guarda tablas completas (HTML) como un solo chunk sin partir, para no romper su estructura al mostrarlas al LLM. Pero el embedding de OpenCLIP trunca a `CLIP_MAX_TOKENS` (200 caracteres, ver `config.py`) — si se embebe el HTML crudo, el vector solo captura las primeras etiquetas (`<table><tr><td>...`), sin contenido útil, y la tabla casi nunca se recupera por similitud semántica. Esto anulaba el beneficio de usar MinerU para tablas.

Se decide generar un texto plano corto (caption + encabezados/primeras celdas) exclusivamente para el embedding, y conservar el HTML completo en el campo de texto que se muestra al LLM en tiempo de retrieval. Requiere un campo separado en el chunk (texto-para-embed vs texto-para-contexto) que hoy no existe en el esquema de metadatos.

## Extensión: OCR fallback para bloques `image` sin caption

Incidente real: una consulta multimodal (imagen de una tabla de tarifas de IVA por país) no citó el dato correcto en la respuesta aunque el RAG recuperó el chunk de la página correcta. Investigación con MinerU real sobre "Guía Tributaria 2 - (IVA) Impuesto al Valor Agregado.pdf" confirmó la causa: en la página de la tabla, MinerU extrae los nombres de país como texto plano ("Argentina", "Perú"...) pero cada porcentaje (21%, 18%...) es un bloque `type: "image"` separado con `image_caption: []` vacío — `_chunks_from_mineru_blocks` descarta esos bloques (`if not text: continue`, ver "Por qué no se graba..." más arriba, mismo principio). El número nunca entra al corpus, ni al texto de display ni al embedding — no es un problema de retrieval ni de generación, el dato no existe en los chunks.

MinerU corre OCR (PaddleOCR embebido) solo sobre regiones que su modelo de layout clasifica como "texto" — nunca sobre las clasificadas como "image", por eso estas badges nunca pasan por ahí. No es específico de este documento: cualquier PDF del corpus con infografías/badges numéricos tiene el mismo problema estructural.

**Decisión**: `rag/chunker.py::_ocr_image_block` corre Tesseract (`pytesseract`) sobre el crop cuando `image_caption` está vacío, y si devuelve texto no vacío lo mete de vuelta en `image_caption` envuelto en un marcador `[img: <texto>]` — fluye por el mismo camino que ya existe para captions reales de MinerU (se intercala en el "run" de párrafo, en orden de lectura). Se prefirió Tesseract sobre reusar Moondream (`VisionAgent`) por-crop: determinístico, sin costo de inferencia LLM, y los crops (círculos con número en alto contraste) son el caso ideal de OCR clásico — un modelo de visión general ya había demostrado dificultad para leer números chicos incluso en la página completa a 768px (ver ADR-0007, corrección relacionada al mismo incidente de imagen).

Detalles empíricos que importan para no romper el fix por accidente:
- El OCR tiene que correr **antes** de que se borre el `tempfile.TemporaryDirectory()` de `chunk_pdf_mineru` — los crops (`img_path`) viven ahí y se pierden al salir del `with`.
- `img_path` es relativo al directorio que contiene `content_list.json`, no al `out_dir` raíz de MinerU (que anida `<out_dir>/<nombre-doc>/<método>/`).
- Preprocesamiento afinado contra crops reales: recortar el 20% del borde de cada lado (el anillo del círculo confunde tanto a Tesseract crudo como a Otsu sin recortar), escalar 5x, binarizar con Otsu adaptativo (`cv2.THRESH_OTSU`, no un umbral fijo — no generaliza entre crops con distinto contraste). Con esa receta: ~8-9 de 9 badges de país se leyeron correctamente en la prueba real (uno, "25%", se leyó "250" — imperfecto pero muy por delante de "ausente por completo").
- Crops puramente decorativos (banderas, íconos, logos) no necesitan heurística de filtro aparte — Tesseract sobre el crop recortado/binarizado naturalmente devuelve vacío o ruido corto, que ya cae en el `if not text: continue` existente.

Config: `MINERU_OCR_IMAGE_FALLBACK` (default `True`) permite desactivar el fallback si Tesseract no está instalado en una máquina dada — degrada al comportamiento anterior (bloques `image` sin caption se descartan).
