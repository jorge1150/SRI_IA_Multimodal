# Despliegue en Azure for Students: dos VMs separadas, ninguna siempre prendida

El tutor de tesis marcó 4 pasos para aspirar a publicación Q1 en vez de Q2: validación humana con expertos tributarios (formulario CREDIT correlacionado con RAGAS), corpus ampliado a 50+ documentos y 100+ consultas, ablación por componente de arquitectura, y reproducibilidad (código + entorno publicados). Los primeros tres requieren compute que la laptop de desarrollo no tiene: MinerU documenta ~16GB RAM para parseo de PDF con tablas/OCR (`requirements.txt`), y la validación con expertos requiere que el sistema sea accesible por una URL, no solo `localhost`.

## Decisión

Desplegar en **Azure for Students** (crédito $100, verificable con correo institucional .edu, sin tarjeta de crédito) usando **dos VMs separadas, ninguna siempre prendida**:

- **VM de ingesta** (CPU-only, 32GB RAM): se prende solo para correr `rag/build_db.py` (MinerU) + `scripts/build_graph.py` sobre el corpus ampliado, sube el resultado (`chroma_db/`+`graph_db/`) a Azure Blob Storage, y se apaga (`az vm deallocate`).
- **VM de demo** (4-8GB RAM, 2 vCPU): se prende solo durante la ventana de evaluación con expertos tributarios (grupo chico, 3-8 personas, en turnos — no concurrencia real), descarga los artefactos del Blob, y se apaga al cerrar la ventana.

## Por qué no una sola VM siempre prendida

El crédito de $100 es finito y el proyecto no tiene presupuesto de producción — una VM grande corriendo 24/7 lo agotaría rápido sirviendo, la mayor parte del tiempo, cero tráfico real (la ingesta es un evento puntual, no continuo; los expertos prueban en una ventana acotada, no todo el mes). Separar por carga de trabajo permite dimensionar cada VM a lo que realmente necesita y apagarla el resto del tiempo.

## Por qué el LLM de texto sigue en Ollama Cloud, no local en la VM de demo

El proyecto ya soporta modelos cloud de Ollama (ADR-0008, cuenta ya activa de Jorge) — la VM de demo delega el modelo de texto grande a Ollama Cloud en vez de servirlo localmente, así que no necesita RAM/GPU dimensionada para eso. `moondream` (visión) no tiene versión `-cloud` y sigue corriendo local vía el mismo daemon Ollama, pero es liviano (~1.6GB) y no cambia el dimensionamiento. Whisper (STT) y Piper (TTS) también siguen 100% locales, sin cambios — ninguno se beneficia de correr en la nube (ADR-0008 ya estableció esto).

## Por qué Docker

Se containeriza la app (`Dockerfile`) y, por separado, el entorno de ingesta con MinerU (`Dockerfile.mineru`, mismo aislamiento numpy<2/numpy>=2 que ya documentaba `requirements.txt` para el venv local `venv_mineru/`). Esto responde directamente al punto 4 del tutor (reproducibilidad: la misma imagen corre en la laptop de Jorge, en la VM de ingesta y en la VM de demo, sin "funciona en mi máquina") y evita reconfigurar manualmente tesseract/portaudio/etc. en cada VM nueva.

## Por qué Azure Blob Storage para mover los artefactos entre VMs

La VM de ingesta y la VM de demo nunca están prendidas al mismo tiempo por diseño (ninguna es "siempre prendida"), así que copiar directo VM-a-VM (scp/rsync) no es viable de forma confiable. Blob Storage desacopla ambas VMs completamente y de paso sirve como backup del corpus construido — si hay que reconstruir la VM de demo, no hace falta volver a correr la ingesta completa.

## Por qué Gradio auth nativo y no VPN/SSH

Los usuarios de la VM de demo son expertos tributarios (contadores), no personal técnico. `gr.Blocks.launch(auth=[(user,pass),...])` da control de acceso suficiente (evitar que la VM quede abierta al público mientras está prendida, sin quemar el crédito de Azure en tráfico de bots) sin pedirles configurar VPN o llaves SSH. La NSG de la VM de demo solo abre el puerto de Gradio (7865) — Ollama (11434) nunca se expone al público.

## Fuera de alcance de esta decisión

El formulario CREDIT en sí, el script de correlación CREDIT↔RAGAS, y la ejecución completa de la matriz de ablación (grafo/agentes/multimodalidad) no forman parte de esta ADR — la infraestructura de despliegue los habilita (VM de ingesta con más compute que la laptop, corpus accesible desde donde se necesite correr `scripts/run_benchmark.py`), pero no los ejecuta ni los diseña.
