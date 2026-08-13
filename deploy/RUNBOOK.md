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

## Dominio + HTTPS — configurar una sola vez

Sin esto la demo funciona igual por `http://<IP>:7865`, pero el navegador
bloquea el micrófono (STT) en HTTP sobre IP pública — hace falta un
"contexto seguro" (HTTPS o localhost). Solución sin comprar dominio: label
DNS gratuito de Azure sobre la IP pública de la VM + `caddy` (HTTPS
automático vía Let's Encrypt, ver `Caddyfile` y `docs/adr/0014`).

Desde tu Mac (la VM de demo tiene que estar prendida y con IP asignada):

```bash
az network public-ip list -g sri-tesis-rg -o table
# copiar el nombre del Public IP de sri-demo-vm

az network public-ip update --resource-group sri-tesis-rg \
  --name <nombre-del-public-ip> --dns-name sri-tesis-demo
# nombre-del-public-ip lo sacás del comando anterior; "sri-tesis-demo" es
# el label que elijas (único en la región eastus) — resultado:
# sri-tesis-demo.eastus.cloudapp.azure.com

az vm open-port --resource-group sri-tesis-rg --name sri-demo-vm --port 80 --priority 890
az vm open-port --resource-group sri-tesis-rg --name sri-demo-vm --port 443 --priority 880
```

Dentro de la VM, agregar el dominio a `.env` (una sola vez, sobrevive a
`git pull`s futuros porque `.env` no está versionado):

```bash
echo 'DOMAIN=sri-tesis-demo.eastus.cloudapp.azure.com' >> .env
cat .env   # confirmar que no quedó duplicada la línea
```

El label sigue funcionando aunque la IP pública cambie al prender/apagar
la VM (está atado al *recurso* Public IP, no al valor) — no hace falta
repetir el `az network public-ip update` cada vez, solo la primera.

## VM de demo — abrir para que los expertos prueben

```bash
# 1. Prender
az vm start --resource-group sri-tesis-rg --name sri-demo-vm

# 2. Conseguir la IP
az vm show -d -g sri-tesis-rg -n sri-demo-vm --query publicIps -o tsv

# 3. Entrar
ssh jorge@<IP-de-arriba>
```

Dentro de la VM (si ya está todo configurado — `.env` con `DOMAIN` y
`GRADIO_AUTH_PAIRS`, Ollama logueado):

```bash
cd ~/SRI_IA_Multimodal
git pull

# Si cambió el corpus desde la última vez, refrescar desde Blob
# (rm -rf primero: download-batch no sobreescribe, y dejar el corpus
# viejo mezclado con el nuevo da resultados corruptos):
rm -rf vector_db graph_db
export AZURE_STORAGE_ACCOUNT=sritesisstorage
export AZURE_STORAGE_KEY="<clave>"
az storage blob download-batch --account-name sritesisstorage \
  --source corpus-artifacts --destination . --pattern "vector_db/*"
az storage blob download-batch --account-name sritesisstorage \
  --source corpus-artifacts --destination . --pattern "graph_db/*"

# --build si cambió requirements.txt, Dockerfile, o el corpus en data/
# (data/ va DENTRO de la imagen, no es un volumen — un `git pull` solo no
# alcanza para que el contenedor lo vea, hace falta rebuildear):
docker compose up -d --build
docker compose logs app --tail 30   # confirmar que arrancó sin error
docker compose logs caddy --tail 20 # confirmar que sacó el cert (busca "certificate obtained successfully")
```

Verificar que responde ANTES de compartir el link (7865 sigue en loopback,
`caddy` es el punto público ahora):

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:7865   # esperar 200 (app, interno)
curl -s -o /dev/null -w "%{http_code}\n" https://$(grep DOMAIN .env | cut -d= -f2)   # esperar 200 (caddy, público)
```

Desde tu Mac, confirmar que también responde desde afuera (no solo desde
adentro de la VM — el NSG puede no estar abierto, ver Troubleshooting):

```bash
curl -sv -m 8 https://sri-tesis-demo.eastus.cloudapp.azure.com
```

Compartir con los expertos: `https://sri-tesis-demo.eastus.cloudapp.azure.com`
(el dominio que hayas elegido) + usuario/clave de `GRADIO_AUTH_PAIRS` en
`.env`. Ya no se comparte la IP ni el puerto 7865.

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
  (30GB) no alcanza — pasó con `Dockerfile.mineru` en la VM de ingesta Y
  con `Dockerfile` (app) en la VM de demo, la imagen `app` sola ya pesa
  ~17GB (torch + wheels CUDA aunque sea CPU-only + transformers + etc.).
  Diagnosticar con `df -h /` y `docker system df` antes de agrandar a lo
  loco — si `docker system df` muestra poco `RECLAIMABLE`, no hay nada
  que limpiar, hay que agrandar el disco: `az vm deallocate` → `az disk
  update --name <disco> --size-gb 64` (nombre real con `az disk list -g
  sri-tesis-rg -o table`) → `az vm start`. Ver `docs/adr/0014`.
- **La "Base de Conocimiento" en la UI sigue mostrando el conteo de docs
  viejo después de un `git pull` que trajo PDFs nuevos**: `data/` NO es un
  volumen montado en `docker-compose.yml` (a diferencia de `vector_db/` y
  `graph_db/`) — se copia DENTRO de la imagen en el build. Un `git pull`
  solo actualiza el archivo en el host; el contenedor corriendo sigue con
  los PDFs que tenía la imagen al buildear. Fix: `docker compose up -d
  --build` (no alcanza `up -d` sin `--build`). Confirmar con `docker
  compose exec app find data -iname "*.pdf" | wc -l`.
- **La demo responde adentro de la VM pero no desde afuera**: falta abrir
  el puerto en el NSG. Con `caddy` (HTTPS) son 80 y 443, no 7865 (ese
  ahora es solo loopback). Verificar con `az network nsg rule list -g
  sri-tesis-rg --nsg-name sri-demo-vmNSG -o table` — si faltan, correr
  `az vm open-port -g sri-tesis-rg -n sri-demo-vm --port 80 --priority
  890` y lo mismo para 443, cada uno solo (no pegado en un bloque con
  otros comandos — a veces no se ejecuta si se pega junto con `az vm
  create`).
- **`caddy` no saca el certificado** (`docker compose logs caddy` no
  muestra "certificate obtained successfully"): casi siempre es que 80
  no está abierto en el NSG (Let's Encrypt necesita el HTTP-01 challenge
  ahí) o que `DOMAIN` en `.env` no coincide exactamente con el label DNS
  configurado en Azure (`az network public-ip show -g sri-tesis-rg --name
  <public-ip> --query dnsSettings.fqdn -o tsv` para confirmar el nombre
  real).
- **`docker logs`/`docker compose logs` no muestran nada**: ya resuelto
  (`PYTHONUNBUFFERED=1` en el `Dockerfile`) — si vuelve a pasar, confirmar
  que la imagen en uso es la actualizada (`docker compose up -d --build`).
- **`.env` con líneas duplicadas** (pasa fácil si se corre `echo ... >>
  .env` dos veces): revisar con `cat .env` después de cualquier edición;
  si hay duplicados, reescribir el archivo entero en vez de parchear.
