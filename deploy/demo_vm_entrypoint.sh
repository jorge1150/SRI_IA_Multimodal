#!/bin/bash
# deploy/demo_vm_entrypoint.sh — corre en la VM de demo (ver deploy/start_stop.md).
#
# Descarga chroma_db/graph_db desde Azure Blob y levanta docker-compose
# (app + ollama). Requiere .env con GRADIO_AUTH_PAIRS seteado (copiar de
# .env.example) y, la primera vez, `docker compose exec ollama ollama signin`
# con la cuenta Ollama Cloud de Jorge.

set -e

STORAGE_ACCOUNT="${AZURE_STORAGE_ACCOUNT:-sritesisstorage}"
CONTAINER="${AZURE_BLOB_CONTAINER:-corpus-artifacts}"

if [ ! -f .env ]; then
  echo "[ERROR] Falta .env — copiar de .env.example y setear GRADIO_AUTH_PAIRS."
  exit 1
fi

echo "[1/4] Descargando vector_db/ + graph_db/ desde Azure Blob..."
mkdir -p vector_db graph_db
az storage blob download-batch \
  --account-name "$STORAGE_ACCOUNT" \
  --source "$CONTAINER" \
  --destination . \
  --pattern "vector_db/*"
az storage blob download-batch \
  --account-name "$STORAGE_ACCOUNT" \
  --source "$CONTAINER" \
  --destination . \
  --pattern "graph_db/*"

echo "[2/4] Levantando docker-compose (app + ollama)..."
docker compose up -d --build

echo "[3/4] Verificando login de Ollama Cloud (necesario solo la primera vez)..."
if ! docker compose exec ollama ollama list >/dev/null 2>&1; then
  echo "  [ADVERTENCIA] Ollama no responde todavía, esperá unos segundos y reintentá."
fi
echo "  Si es la primera vez en esta VM, correr:"
echo "    docker compose exec ollama ollama signin"
echo "    docker compose exec ollama ollama pull moondream"

echo "[4/4] Listo. UI en http://<IP-publica-VM>:7865"
echo "  Compartir con los expertos junto con las credenciales de GRADIO_AUTH_PAIRS."
echo "  Al terminar la ventana de evaluación:"
echo "    docker compose down"
echo "    az vm deallocate --resource-group sri-tesis-rg --name sri-demo-vm"
