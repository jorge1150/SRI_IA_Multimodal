# Runbook — operar las VMs día a día

Guía rápida de "ya está todo creado, solo quiero prender/usar/apagar".
Para crear las VMs desde cero la primera vez, ver `deploy/azure_setup.md`
(cuenta/storage) y `deploy/start_stop.md` (comandos de creación completos).
Contexto de por qué existen dos VMs separadas: `docs/adr/0014-despliegue-cloud-azure.md`.

## Referencia rápida

| VM | Nombre | Tamaño | Uso | IP pública |
|---|---|---|---|---|
| Ingesta | `sri-ingest-vm` | `Standard_E4s_v3` (4 vCPU/32GB) | Construir corpus con MinerU + GraphRAG, subir a Blob | dinámica, revisar cada vez |
| Demo | `sri-demo-vm` | `Standard_B2s` (2 vCPU/4GB) | UI Gradio para expertos tributarios | dinámica, revisar cada vez |

Storage: cuenta `sritesisstorage`, container `corpus-artifacts`, resource
group `sri-tesis-rg`, región `eastus`.

## Ver estado de ambas VMs

```bash
az vm list -d --resource-group sri-tesis-rg --output table
```

Columna `PowerState` — `VM running` (cobrando) o `VM deallocated` (no
cobrando). Revisar esto es el primer paso ante cualquier duda de "¿algo
quedó prendido por accidente?".

## VM de ingesta — correr una ingesta nueva (ej. tras ampliar el corpus)

```bash
# 1. Prender
az vm start --resource-group sri-tesis-rg --name sri-ingest-vm

# 2. Conseguir la IP (cambia cada vez que se apaga/prende)
az vm show -d -g sri-tesis-rg -n sri-ingest-vm --query publicIps -o tsv

# 3. Entrar
ssh jorge@<IP-de-arriba>
```

Dentro de la VM:

```bash
cd ~/SRI_IA_Multimodal
git pull                              # traer cambios de código/corpus más recientes
export AZURE_STORAGE_ACCOUNT=sritesisstorage
export AZURE_STORAGE_KEY="<clave — ver comando abajo>"

tmux new -s ingesta                   # sobrevive si se corta el ssh
bash deploy/ingest_vm_run.sh
# Ctrl+B, D para salir del tmux sin matar el proceso
# tmux attach -t ingesta para volver a entrar
```

Clave de Storage (correr en tu Mac si no la tenés a mano):

```bash
az storage account keys list --account-name sritesisstorage \
  --resource-group sri-tesis-rg --query "[0].value" -o tsv
```

Al terminar (confirmar que subió a Blob antes de apagar):

```bash
az storage blob list --account-name sritesisstorage \
  --container-name corpus-artifacts --output table

exit   # salir de la VM
az vm deallocate --resource-group sri-tesis-rg --name sri-ingest-vm
```

## VM de demo — abrir para que los expertos prueben

```bash
# 1. Prender
az vm start --resource-group sri-tesis-rg --name sri-demo-vm

# 2. Conseguir la IP
az vm show -d -g sri-tesis-rg -n sri-demo-vm --query publicIps -o tsv

# 3. Entrar
ssh jorge@<IP-de-arriba>
```

Dentro de la VM (si ya está todo configurado — `.env`, Ollama logueado):

```bash
cd ~/SRI_IA_Multimodal
git pull

# Si cambió el corpus desde la última vez, refrescar desde Blob:
export AZURE_STORAGE_ACCOUNT=sritesisstorage
export AZURE_STORAGE_KEY="<clave>"
az storage blob download-batch --account-name sritesisstorage \
  --source corpus-artifacts --destination . --pattern "vector_db/*"
az storage blob download-batch --account-name sritesisstorage \
  --source corpus-artifacts --destination . --pattern "graph_db/*"

docker compose up -d
docker compose logs app --tail 30   # confirmar que arrancó sin error
```

Verificar que responde ANTES de compartir el link:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:7865   # esperar 200
```

Desde tu Mac, confirmar que también responde desde afuera (no solo desde
adentro de la VM — el NSG puede no estar abierto, ver Troubleshooting):

```bash
curl -sv -m 8 http://<IP-de-la-VM>:7865
```

Compartir con los expertos: `http://<IP-de-la-VM>:7865` + usuario/clave de
`GRADIO_AUTH_PAIRS` en `.env`.

Al terminar la ventana de evaluación:

```bash
docker compose down
exit
az vm deallocate --resource-group sri-tesis-rg --name sri-demo-vm
```

## Prender un flag de config sin reconstruir la imagen

Cualquier variable de `config.py` que lea `os.getenv(...)` (`USE_AGENTIC_PLANNER`,
`REFINEMENT_MAX_ITERATIONS`, etc.) se puede activar agregando una línea al
`.env` de la VM de demo — `docker-compose.yml` las pasa automáticamente al
contenedor (`env_file: .env`), no hace falta tocar código ni la imagen:

```bash
echo 'USE_AGENTIC_PLANNER=true' >> .env
cat .env                    # confirmar que no quedó duplicada la línea
docker compose up -d        # recrea el contenedor con el env nuevo, SIN --build
```

## Troubleshooting rápido

- **`QuotaExceeded` al crear una VM**: correr `az vm list-usage --location
  eastus --output table`, buscar una familia con `Limit` > 0 y usar un
  tamaño de esa familia. Ver detalle en `deploy/start_stop.md`.
- **`no space left on device` en un build de Docker**: el disco default
  (30GB) no alcanza para `Dockerfile.mineru`. Agrandar con `az disk update
  --size-gb 64` (VM deallocated primero). Ver `docs/adr/0014`.
- **La demo responde adentro de la VM pero no desde afuera**: el puerto
  7865 no está abierto en el NSG. Verificar con `az network nsg rule list
  -g sri-tesis-rg --nsg-name sri-demo-vmNSG -o table` — si solo aparece el
  puerto 22, correr `az vm open-port -g sri-tesis-rg -n sri-demo-vm --port
  7865 --priority 900` de nuevo, solo (no pegado en un bloque con otros
  comandos — a veces no se ejecuta si se pega junto con `az vm create`).
- **`docker logs`/`docker compose logs` no muestran nada**: ya resuelto
  (`PYTHONUNBUFFERED=1` en el `Dockerfile`) — si vuelve a pasar, confirmar
  que la imagen en uso es la actualizada (`docker compose up -d --build`).
- **`.env` con líneas duplicadas** (pasa fácil si se corre `echo ... >>
  .env` dos veces): revisar con `cat .env` después de cualquier edición;
  si hay duplicados, reescribir el archivo entero en vez de parchear.
