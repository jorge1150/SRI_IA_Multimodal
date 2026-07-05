# Corte del corpus a 20 documentos curados, reemplaza al corpus de 176

El corpus de desarrollo (176 documentos, 9.448 fragmentos, documentado en `docs/arquitectura_tecnica.md`) se reemplaza por completo por un corpus curado de ~20 PDFs seleccionados para la tesis. Las carpetas `data/normativas_sri/`, `data/resoluciones/`, `data/guias_tributarias/`, `data/formularios/` se limpian antes de cargar los 20 documentos finales — no conviven ambos corpus.

Consecuencia: todas las métricas ya documentadas (fragmentos, entidades, relaciones, triples) quedan obsoletas y deben recalcularse tras la reingesta con MinerU (ver ADR-0001) sobre el corpus nuevo.
