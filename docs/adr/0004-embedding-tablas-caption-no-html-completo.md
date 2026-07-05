# Embeddings de chunks-tabla usan un caption/resumen, no el HTML completo

`chunk_pdf_mineru` guarda tablas completas (HTML) como un solo chunk sin partir, para no romper su estructura al mostrarlas al LLM. Pero el embedding de OpenCLIP trunca a `CLIP_MAX_TOKENS` (200 caracteres, ver `config.py`) — si se embebe el HTML crudo, el vector solo captura las primeras etiquetas (`<table><tr><td>...`), sin contenido útil, y la tabla casi nunca se recupera por similitud semántica. Esto anulaba el beneficio de usar MinerU para tablas.

Se decide generar un texto plano corto (caption + encabezados/primeras celdas) exclusivamente para el embedding, y conservar el HTML completo en el campo de texto que se muestra al LLM en tiempo de retrieval. Requiere un campo separado en el chunk (texto-para-embed vs texto-para-contexto) que hoy no existe en el esquema de metadatos.
