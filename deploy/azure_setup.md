# Setup de Azure for Students — paso a paso

Cuenta nueva, sin experiencia previa en Azure. Ver contexto completo en
`docs/adr/0014-despliegue-cloud-azure.md`.

## 1. Activar el crédito de estudiante

1. Ir a https://azure.microsoft.com/free/students/
2. Verificar con el correo institucional .edu — sin tarjeta de crédito.
3. Confirma $100 de crédito, válido 12 meses.

## 2. Instalar y autenticar Azure CLI (en tu Mac)

```bash
brew install azure-cli
az login          # abre el navegador para loguearte con la misma cuenta
az account show   # confirma que apunta a la suscripción "Azure for Students"
```

## 3. Crear un Resource Group

Agrupa todos los recursos de este proyecto para poder borrarlos juntos si
hace falta.

```bash
az group create --name sri-tesis-rg --location eastus
```

(`eastus` es barata y confiable; cambiar si tu universidad recomienda otra
región. Ver precios: https://azure.microsoft.com/pricing/details/virtual-machines/linux/)

## 4. Crear Storage Account + Blob Container

Para mover `chroma_db/`+`graph_db/` entre la VM de ingesta y la VM de demo.

⚠️ En subscripciones nuevas (p.ej. Azure for Students recién activada) el
primer `az storage account create` puede fallar con
`(SubscriptionNotFound) Subscription ... was not found` porque el resource
provider `Microsoft.Storage` aún no está registrado. Si eso pasa:

```bash
az provider register --namespace Microsoft.Storage

# esperar a que diga "Registered" (puede tardar 1-2 min)
az provider show --namespace Microsoft.Storage --query registrationState -o tsv
```

Luego reintentar el comando de abajo.

```bash
az storage account create \
  --name sritesisstorage \
  --resource-group sri-tesis-rg \
  --location eastus \
  --sku Standard_LRS

az storage container create \
  --account-name sritesisstorage \
  --name corpus-artifacts \
  --auth-mode login
```

## 5. Comandos de referencia rápida

Guardar la clave de acceso para subir/bajar blobs sin loguearte cada vez:

```bash
az storage account keys list \
  --account-name sritesisstorage \
  --resource-group sri-tesis-rg \
  --query "[0].value" -o tsv
```

Subir (desde la VM de ingesta, tras el build):

```bash
az storage blob upload-batch \
  --account-name sritesisstorage \
  --destination corpus-artifacts \
  --source ./vector_db \
  --destination-path vector_db
```

Descargar (en la VM de demo, al prender):

```bash
az storage blob download-batch \
  --account-name sritesisstorage \
  --source corpus-artifacts \
  --destination ./vector_db \
  --pattern "vector_db/*"
```

## 6. Siguiente paso

Con esto listo, seguir con `deploy/ingest_vm_run.sh` (VM de ingesta) y
`deploy/demo_vm_entrypoint.sh` (VM de demo). Comandos de crear/prender/
apagar cada VM viven en `deploy/start_stop.md`.
