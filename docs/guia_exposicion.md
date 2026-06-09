# Guía de Exposición Académica — SRI IA Multimodal

**Asistente Virtual Basado en RAG Multimodal para Normativa Tributaria del SRI Ecuador**  
Maestría en Inteligencia Artificial Aplicada · UIsrael

---

## Estructura de la Presentación (20-30 minutos)

### 1. Introducción y Motivación (3-5 min)

**Problema que resuelve:**
- La normativa tributaria ecuatoriana es extensa, cambia frecuentemente y es difícil de consultar para contribuyentes y asesores.
- El SRI tiene leyes, reglamentos, resoluciones, guías y formularios dispersos en múltiples fuentes.
- Consultar un abogado tributario tiene un costo elevado para pequeños contribuyentes.

**Solución propuesta:**
- Asistente IA local que responde consultas sobre normativa tributaria citando la fuente exacta.
- No depende de internet en tiempo de ejecución (privacidad y disponibilidad offline).
- Multimodal: acepta texto, voz, imagen (formularios, portal SRI) y video.

---

### 2. Arquitectura del Sistema (5-7 min)

**Mostrar diagrama del pipeline:**

```
Consulta del usuario
       ↓
[Multimodal: Texto + Voz + Imagen + Video]
       ↓
[OpenCLIP] → Vector semántico
       ↓
[ChromaDB] → Fragmentos normativos relevantes
  (con metadatos: ley, artículo, página)
       ↓
[TinyLlama vía Ollama] → Respuesta con citas
       ↓
[Piper TTS] → Audio en español ecuatoriano
```

**Puntos clave a destacar:**
- Todo funciona localmente (sin APIs de pago, sin internet obligatorio)
- ChromaDB almacena embeddings vectoriales de la normativa
- Los metadatos permiten citar la fuente exacta: ley, artículo y página
- El prompt obliga al LLM a no inventar información no respaldada

---

### 3. Demostración en Vivo (8-10 min)

**Demo 1: Consulta por texto simple**
- Escribe: "¿Cuál es la tarifa actual del IVA en Ecuador?"
- Muestra: respuesta con cita LORTI Art. 65
- Señala en los logs: RAG recupera fragmento de iva_lorti.txt

**Demo 2: Consulta por voz**
- Habla: "¿Cuáles son los plazos para declarar el IVA?"
- Muestra: transcripción Whisper → respuesta → audio Piper TTS
- Señala en los logs: flujo STT → RAG → GENERANDO → TTS

**Demo 3: Análisis de imagen (formulario)**
- Captura la pantalla o sube imagen del Formulario 104
- Escribe: "¿Qué significa esta casilla?"
- Muestra: Moondream describe la imagen → RAG busca instructivo → respuesta contextual

**Demo 4: Consulta sin normativa disponible**
- Pregunta sobre un tema no cargado en la BD
- Muestra: el sistema dice "No encontré normativa específica sobre este tema"
- Enfatiza: el sistema NO inventa información

---

### 4. Innovaciones Técnicas (3-4 min)

**Metadatos ricos en el RAG:**
- A diferencia de sistemas genéricos, cada fragmento tiene: nombre del documento, tipo de normativa, año, artículo/sección y número de página.
- Esto permite citas precisas: "Según la Ley de Régimen Tributario Interno, Art. 65, Pág. 23..."

**Keyword Reranking tributario:**
- Después de la búsqueda vectorial, se aplica un re-ranking por palabras clave del dominio.
- Compensa las limitaciones de CLIP (modelo de visión) para texto legal especializado.

**Soporte multiformat:**
- El sistema procesa PDFs (con número de página), DOCX, TXT y MD.
- PyMuPDF extrae texto página por página para una cita precisa.

**Prompt con restricciones legales:**
- El prompt del sistema prohíbe explícitamente inventar artículos, porcentajes o plazos.
- Obliga a decir cuándo no hay información suficiente.
- Incluye disclaimer de asesoría no vinculante.

---

### 5. Comparación con el Proyecto Base (2-3 min)

**S3 IA Multimodal (soporte técnico PC) → SRI IA Multimodal (normativa tributaria):**

| Aspecto | S3 IA (base) | SRI IA (nuevo) |
|---|---|---|
| Dominio | Fallas de computadora | Leyes y normativas tributarias |
| Documentos | TXT manuales simples | PDF/DOCX legales con paginación |
| Metadatos | source, id | + tipo, año, artículo, página |
| Citas de fuente | No | Sí (obligatorio por prompt) |
| Disclaimer | No | Sí (ético y legal) |
| Carpetas | 1 carpeta manuals/ | 4 categorías normativas |

---

### 6. Conclusiones y Trabajo Futuro (2-3 min)

**Logros:**
- Sistema RAG multimodal funcional y 100% local.
- Respuestas que citan la fuente exacta de la normativa.
- Soporte para PDF, DOCX, TXT y MD del SRI.
- Interfaz profesional con logs de trazabilidad.

**Limitaciones actuales:**
- TinyLlama tiene capacidad de razonamiento limitada (puede cometerse errores en lógica compleja).
- OpenCLIP es un modelo de visión, no optimizado para texto legal — el reranking compensa esto.
- La calidad de las respuestas depende de qué documentos se hayan cargado.

**Mejoras propuestas:**
- Usar un LLM más capaz (Llama 3, Mistral) cuando el hardware lo permita.
- Implementar un embedder de texto especializado en español legal (e.g., multilingual-e5).
- Agregar actualización automática de normativa desde sri.gob.ec.
- Interfaz de administración para cargar nuevos documentos desde la UI.

---

## Preguntas Frecuentes del Jurado

**¿Por qué usar RAG en lugar de fine-tuning?**
La normativa tributaria cambia frecuentemente (nuevas resoluciones, cambios en tarifas). El RAG permite actualizar el conocimiento cargando nuevos documentos sin reentrenar el modelo. El fine-tuning requiere datos etiquetados y tiempo de entrenamiento para cada actualización.

**¿Cómo garantiza que no invente normativa?**
El prompt del sistema tiene restricciones explícitas: el LLM DEBE basarse solo en el contexto RAG recuperado. Si no hay normativa en el contexto, el sistema está programado para decirlo claramente y recomendar consultar sri.gob.ec.

**¿Por qué OpenCLIP y no un embedder de texto?**
El proyecto reutiliza la arquitectura del S3 IA Multimodal que usa OpenCLIP para compatibilidad multimodal (texto + imagen). El keyword reranking compensa sus limitaciones en texto especializado. Una mejora futura sería usar sentence-transformers con modelos de español.

**¿Qué pasa si la normativa del SRI cambia?**
El sistema es agnóstico al contenido: simplemente se cargan los nuevos documentos en las carpetas data/ y se ejecuta `python rag/build_db.py --reset`. En minutos la base vectorial está actualizada con la nueva normativa.

**¿Funciona con documentos en otro idioma?**
El sistema está configurado para español (Whisper con idioma español). Los documentos en inglés o quechua no tendrían respuestas óptimas, pero el sistema no falla — simplemente tendrá menor precisión.

---

## Comandos Clave para la Demo

```bash
# Iniciar Ollama (en terminal separada)
ollama serve

# Verificar que los modelos estén disponibles
ollama list

# Construir/actualizar base vectorial
python rag/build_db.py

# Lanzar el asistente
source venv/bin/activate
python app.py
# → Abrir http://localhost:7865
```
