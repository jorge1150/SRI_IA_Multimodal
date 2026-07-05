# MinerU como backend de parseo PDF por defecto, PyMuPDF solo como fallback

El proyecto evalúa calidad de conversión documento→RAG, no velocidad de ingesta. MinerU reconoce layout, tablas (HTML) y aplica OCR, a diferencia de PyMuPDF que solo extrae texto plano por página. Se decidió usar MinerU siempre (`USE_MINERU_PDF` debe ser `true` por defecto) sobre el corpus de tesis (~20 documentos), y dejar PyMuPDF únicamente como fallback automático si MinerU falla en un documento puntual — no como backend principal.

Costo aceptado: ingesta más lenta por documento (modelos de layout/OCR en CPU, Mac Intel sin GPU) a cambio de mejor fragmentación de tablas y texto con estructura compleja.
