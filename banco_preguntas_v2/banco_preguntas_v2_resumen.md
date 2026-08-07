# Banco de Preguntas v2 — Resumen

Fecha de consulta: 2026-08-04 (q06 corregida y re-verificada el 2026-08-06 — ver nota abajo). 20 preguntas nuevas de evaluación RAGAS sobre normativa tributaria ecuatoriana (SRI), generadas para el proyecto GraphRAG multimodal, evitando duplicar temas/documentos ya presentes en `preguntas.docx`.

**Corrección q06 (2026-08-06)**: la respuesta original citaba el plazo original de la Resolución NAC-DGERCGC25-00000014 (día 10), sin detectar que fue modificado a día 7 por la Resolución NAC-DGERCGC25-00000017 (vigente desde 01-ago-2025). Corregido tras revisión de experto contador y verificación directa del PDF oficial de la reforma.

| ID | Categoría | Pregunta | Documento fuente | Artículo/Norma |
|----|-----------|----------|-------------------|----------------|
| q01 | RIMPE | Tengo un cliente que es negocio popular dentro del RIMPE y me pregunta si puede seguir emitiendo notas de venta preimpresas o si ya está obligado a facturar electrónicamente. ¿Qué le respondo? | `RIMPE_normas_aplicacion_NAC-DGERCGC24-00000027.pdf` | Art. 6 de la Resolución Nro. NAC-DGERCGC24-00000027 |
| q02 | RIMPE | Una sociedad cliente mía está catalogada como RIMPE Emprendedor y su RUC tiene noveno dígito 5. ¿Hasta qué fecha debe declarar y pagar su Impuesto a la Renta anual? | `RIMPE_normas_aplicacion_NAC-DGERCGC24-00000027.pdf` | Art. 8 de la Resolución Nro. NAC-DGERCGC24-00000027 |
| q03 | RIMPE | ¿Existe un límite de tiempo para que un contribuyente "emprendedor" se mantenga dentro del RIMPE, o puede quedarse indefinidamente si le conviene tributariamente? | `rimpe_reglamento_ley_desarrollo_covid_titulo_iv.pdf` | Art. 217 del Reglamento para la Aplicación de la LRTI (Título IV RIMPE, incorporado por el Reglamento a la Ley Orgánica para el Desarrollo Económico y Sostenibilidad Fiscal tras la Pandemia COVID-19) |
| q04 | RIMPE | Mi empresa (régimen general) le compró mercadería a un negocio popular del RIMPE, que me entregó una nota de venta. ¿Puedo usar el IVA de esa compra como crédito tributario directamente con esa nota de venta? | `rimpe_reglamento_ley_desarrollo_covid_titulo_iv.pdf` | Art. 224 del Reglamento para la Aplicación de la LRTI (Título IV RIMPE) |
| q05 | Facturación electrónica | Emito facturas electrónicas y hasta hace poco sabía que tenía hasta 4 días hábiles para transmitirlas al SRI. Un colega me dijo que eso cambió. ¿Cuál es el plazo vigente para transmitir mis comprobantes electrónicos? | `facturacion_electronica_NAC-DGERCGC25-00000014.pdf` | Disposición Reformatoria Primera, numeral 2, de la Resolución NAC-DGERCGC25-00000014 (que reforma el Art. 7 de la Resolución NAC-DGERCGC18-00000233) |
| q06 | Facturación electrónica | Emití una factura electrónica en julio con un error y recién ahora en agosto me di cuenta. ¿Hasta qué fecha puedo anularla en línea sin tener que emitir una nota de crédito? | `NAC-DGERCGC25-00000017.pdf` | Art. 3 de la Resolución NAC-DGERCGC25-00000014, reformado por el Art. 1.a).1 de la Resolución NAC-DGERCGC25-00000017: "el día 10" → "el día 7 (siete)", vigente desde el 01-ago-2025 |
| q07 | Facturación electrónica | Le envié a mi proveedor una solicitud de anulación de un comprobante de retención electrónico y no me ha respondido. ¿Cuánto tiempo tiene para aceptar o rechazar antes de que la solicitud quede sin efecto? | `facturacion_electronica_NAC-DGERCGC25-00000014.pdf` | Art. 4 de la Resolución NAC-DGERCGC25-00000014 |
| q08 | Facturación electrónica | Un cliente nuevo me comenta que no ha presentado declaraciones de impuestos en los últimos 6 meses. ¿Eso le puede afectar la autorización para emitir sus comprobantes de venta y cuánto dura normalmente esa autorización? | `reglamento_comprobantes_venta_retencion.pdf` | Art. 6 del Reglamento de Comprobantes de Venta, Retención y Documentos Complementarios |
| q09 | Retenciones en la fuente | Voy a pagar honorarios a un abogado independiente (persona natural) por asesoría legal. ¿Qué porcentaje de retención en la fuente de Impuesto a la Renta debo aplicarle? | `retenciones_fuente_ir_2026.pdf` | Art. 2, numeral 7, literal a) de la Resolución NAC-DGERCGC26-00000009 |
| q10 | Retenciones en la fuente | La empresa donde trabajo arrienda una oficina a una persona natural. ¿Qué porcentaje de retención de Impuesto a la Renta debemos aplicar sobre el canon mensual de arrendamiento? | `retenciones_fuente_ir_2026.pdf` | Art. 2, numeral 7, literal g) de la Resolución NAC-DGERCGC26-00000009 |
| q11 | Retenciones en la fuente | Contratamos a una compañía consultora (sociedad) para que nos preste servicios profesionales de auditoría. ¿A qué porcentaje de retención de Impuesto a la Renta está sujeto ese pago? | `retenciones_fuente_ir_2026.pdf` | Art. 2, numeral 6, literal a) de la Resolución NAC-DGERCGC26-00000009 |
| q12 | Retenciones en la fuente | Voy a pagar por un concepto que no logro ubicar en ninguno de los porcentajes específicos de la tabla de retenciones de Impuesto a la Renta. ¿Qué porcentaje aplico por defecto? | `retenciones_fuente_ir_2026.pdf` | Art. 3 de la Resolución NAC-DGERCGC26-00000009 |
| q13 | IVA | Mi negocio se dedica exclusivamente a la venta de productos agrícolas en estado natural, gravados con tarifa 0% de IVA. ¿Debo declarar el IVA todos los meses o puedo hacerlo semestralmente? | `reglamento_lrti_2023_declaracion_iva_art158.pdf` | Art. 158 del Reglamento para la Aplicación de la LRTI (Capítulo III: Declaración, liquidación y pago del IVA) |
| q14 | IVA | Tengo una farmacia y vendo medicamentos de uso humano. ¿Esas ventas están gravadas con la tarifa general de IVA o con tarifa 0%? | `lrti_texto_vigente_sri_tarifa0_exportadores.pdf` | Art. 55, numeral 6, de la Ley de Régimen Tributario Interno |
| q15 | IVA | Un cliente mío, persona natural, arrienda su departamento exclusivamente para vivienda. ¿Debe facturar ese arriendo con IVA? | `lrti_texto_vigente_sri_tarifa0_exportadores.pdf` | Art. 56, numeral 3, de la Ley de Régimen Tributario Interno |
| q16 | IVA | Una empresa exportadora de cacao pagó IVA en la compra local de materia prima e insumos para el producto que exporta. ¿Tiene derecho a recuperar ese IVA y cómo lo solicita? | `lrti_texto_vigente_sri_tarifa0_exportadores.pdf` | Art. 57 de la Ley de Régimen Tributario Interno |
| q17 | Impuesto a la Renta | Para la declaración del Impuesto a la Renta del ejercicio fiscal 2026, ¿hasta qué monto de ingresos una persona natural no paga impuesto (fracción básica exenta)? | `tabla_impuesto_renta_personas_naturales_2026.pdf` | Tabla de Impuesto a la Renta Personas Naturales, Año 2026, conforme la Resolución Nro. NAC-DGERCGC25-00000043 |
| q18 | Impuesto a la Renta | Una sociedad cliente me pregunta si está obligada a pagar un anticipo de Impuesto a la Renta durante el año. ¿Es obligatorio o voluntario, y cómo se calcula si decide hacerlo? | `lrti_texto_vigente_sri_tarifa0_exportadores.pdf` | Art. 41 de la Ley de Régimen Tributario Interno (Pago del impuesto) |
| q19 | Impuesto a la Renta | Una sociedad cuyo RUC tiene noveno dígito 7, del régimen general (no RIMPE), ¿hasta qué fecha debe presentar y pagar su declaración anual de Impuesto a la Renta? | `reglamento_lrti_2023_declaracion_iva_art158.pdf` | Art. 72, numeral 1, del Reglamento para la Aplicación de la LRTI |
| q20 | Impuesto a la Renta | Un comisionista (persona natural) inició el ejercicio fiscal con activos menos pasivos relacionados con su actividad por USD 190.000. ¿Está obligado a llevar contabilidad? | `reglamento_lrti_2023_declaracion_iva_art158.pdf` | Art. 37 del Reglamento para la Aplicación de la LRTI (Capítulo V: De la contabilidad) |

## Conteo por categoría

- **RIMPE**: 4 preguntas
- **Facturación electrónica**: 4 preguntas
- **Retenciones en la fuente**: 4 preguntas
- **IVA**: 4 preguntas
- **Impuesto a la Renta**: 4 preguntas

## PDFs fuente descargados en `data/pdfs_actualizados/`

- `NAC-DGERCGC25-00000017.pdf` (reforma del plazo de anulación, añadido 2026-08-06)
- `RIMPE_normas_aplicacion_NAC-DGERCGC24-00000027.pdf`
- `facturacion_electronica_NAC-DGERCGC25-00000014.pdf`
- `lrti_texto_vigente_sri_tarifa0_exportadores.pdf`
- `reglamento_comprobantes_venta_retencion.pdf`
- `reglamento_lrti_2023_declaracion_iva_art158.pdf` (fuente también de q19/q20 — ver nota_verificacion en el JSON)
- `retenciones_fuente_ir_2026.pdf`
- `rimpe_reglamento_ley_desarrollo_covid_titulo_iv.pdf`
- `tabla_impuesto_renta_personas_naturales_2026.pdf`
