#!/bin/bash
# deploy/ingest_vm_run.sh — corre en la VM de ingesta (ver deploy/start_stop.md).
#
# Construye chroma_db/ + graph_db/ con MinerU sobre el corpus en data/ y
# los sube a Azure Blob Storage. Primera corrida: probar con un subset
# chico de data/ (5 docs) antes del corpus completo de 50+, para calibrar
# tiempo/memoria reales en esta VM (ver Fase 2 del plan de despliegue).

set -e

STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-sritesisstorage}"
CONTAINER="${AZURE_BLOB_CONTAINER:-corpus-artifacts}"

echo "[1/5] Verificando Docker..."
command -v docker >/dev/null || { echo "Docker no instalado. Ver README de la VM."; exit 1; }

echo "[2/5] Build de la imagen de ingesta (Dockerfile.mineru)..."
docker build -f Dockerfile.mineru -t sri-ia-mineru .

echo "[3/5] Corriendo build_db.py (MinerU) + build_graph.py dentro del contenedor..."
docker run --rm \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/vector_db:/app/vector_db" \
  -v "$(pwd)/graph_db:/app/graph_db" \
  -e USE_MINERU_PDF=true \
  sri-ia-mineru \
  bash -c "python rag/build_db.py && python scripts/build_graph.py"

echo "[4/5] Subiendo vector_db/ + graph_db/ a Azure Blob ($STORAGE_ACCOUNT/$CONTAINER)..."
az storage blob upload-batch \
  --account-name "$STORAGE_ACCOUNT" \
  --destination "$CONTAINER" \
  --source ./vector_db \
  --destination-path vector_db \
  --overwrite

az storage blob upload-batch \
  --account-name "$STORAGE_ACCOUNT" \
  --destination "$CONTAINER" \
  --source ./graph_db \
  --destination-path graph_db \
  --overwrite

echo "[5/5] Listo. Recordá: az vm deallocate --resource-group sri-tesis-rg --name sri-ingest-vm"
