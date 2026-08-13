# Prender / apagar las VMs — control de costo

Ninguna VM queda siempre prendida (ver docs/adr/0014). `az vm deallocate`
libera el cómputo (deja de cobrar por vCPU/RAM) pero conserva el disco —
`az vm delete` sí borra todo, no usar salvo que quieras destruir la VM
definitivamente.

## VM de ingesta (crear una vez, prender/apagar por corrida)

Crear (primera vez):

```bash
az vm create \
  --resource-group sri-tesis-rg \
  --name sri-ingest-vm \
  --image Ubuntu2204 \
  --size Standard_E4s_v3 \
  --os-disk-size-gb 64 \
  --admin-username jorge \
  --generate-ssh-keys
```

⚠️ Suscripciones nuevas de Azure for Students traen **límite total de 6
vCPU por región** (cuota "Total Regional Cores") Y ADEMÁS cada familia de
VM tiene su propia cuota separada, casi todas en 0 por default — confirmar
siempre con `az vm list-usage --location eastus --output table` antes de
elegir tamaño. `Standard_D8as_v5` (8 vCPU) y `Standard_E4as_v5` (familia
EASv5, cuota 0) fallaron ambos con `QuotaExceeded`. `Standard_E4s_v3` sí
funciona: familia "Standard ESv3" tiene cuota real de 4, da 4 vCPU/32GB
RAM (memory-optimized, 8GB/core — mismo target de RAM), y deja 2 vCPU
libres del total regional para la VM de demo (`B2s`) sin volver a chocar
el límite. Si más adelante hace falta más CPU, pedir aumento de cuota
desde el link que da el propio error de `QuotaExceeded` (puede tardar en
aprobarse, no asumir que es instantáneo).

⚠️ `--os-disk-size-gb 64`: el disco default (30GB) se llenó a mitad del
build de `Dockerfile.mineru` (`no space left on device`) — mineru[pipeline]
baja ~20GB de modelos/deps (incluye paquetes NVIDIA/CUDA aunque el proyecto
corra CPU-only, son dependencias transitorias del paquete). Si ya creaste
la VM sin este flag, se resuelve sin recrearla: `az vm deallocate` → `az
disk update --name <nombre-del-os-disk> --size-gb 64` (nombre real con `az
disk list -g sri-tesis-rg -o table`) → `az vm start` — Ubuntu/Azure crece
el filesystem solo al bootear, no hace falta `growpart` manual.

Prender / correr ingesta / apagar (cada vez que actualices el corpus):

```bash
az vm start --resource-group sri-tesis-rg --name sri-ingest-vm
ssh jorge@$(az vm show -d -g sri-tesis-rg -n sri-ingest-vm --query publicIps -o tsv)
# dentro de la VM: bash deploy/ingest_vm_run.sh
az vm deallocate --resource-group sri-tesis-rg --name sri-ingest-vm
```

Costo aproximado: `Standard_E4s_v3` ronda USD ~0.20-0.25/hora en `eastus`
(confirmar precio vigente en el portal — cambia por región/hora). Una
corrida completa de 50+ docs con MinerU puede tardar varias horas en
CPU-only: validar primero con el corpus chico actual (10 docs) para
calibrar tiempo real antes de dejarla corriendo desatendida con el corpus
ampliado.

## VM de demo (crear una vez, prender/apagar por ventana de evaluación)

Crear (primera vez):

```bash
az vm create \
  --resource-group sri-tesis-rg \
  --name sri-demo-vm \
  --image Ubuntu2204 \
  --size Standard_B2s \
  --admin-username jorge \
  --generate-ssh-keys

# Abrir SOLO el puerto de Gradio, nunca Ollama (11434):
az vm open-port --resource-group sri-tesis-rg --name sri-demo-vm --port 7865
```

Prender antes de la sesión con expertos / apagar al terminar:

```bash
az vm start --resource-group sri-tesis-rg --name sri-demo-vm
ssh jorge@$(az vm show -d -g sri-tesis-rg -n sri-demo-vm --query publicIps -o tsv)
# dentro de la VM: bash deploy/demo_vm_entrypoint.sh
# ... compartir http://<IP>:7865 + credenciales con los expertos ...
az vm deallocate --resource-group sri-tesis-rg --name sri-demo-vm
```

Costo aproximado: `Standard_B2s` ronda USD ~0.04-0.05/hora — dejarla
prendida una tarde completa de evaluación es centavos, no un problema real
de presupuesto. El riesgo de costo real está en la VM de ingesta (más
grande) quedando prendida por olvido — confirmar siempre el `deallocate`
al terminar cada corrida.

⚠️ La IP pública es dinámica — puede cambiar cada vez que se hace
`deallocate`/`start` (no cambia mientras la VM sigue prendida entre
sesiones de la misma ventana de evaluación). Siempre reconfirmar con `az
vm show -d -g sri-tesis-rg -n sri-demo-vm --query publicIps -o tsv` antes
de compartir el link con los expertos, no reusar una IP vieja de memoria.

⚠️ Confirmar que el puerto quedó realmente abierto después de crear la VM
— `az vm open-port` pegado en el mismo bloque que `az vm create` puede no
ejecutarse si el terminal interpreta mal el bloque multilínea. Verificar
con `az network nsg rule list -g sri-tesis-rg --nsg-name sri-demo-vmNSG -o
table` (debe listar una regla para el puerto 7865, no solo `22`) antes de
asumir que la demo es alcanzable desde afuera.

## Revisar gasto de crédito

```bash
az consumption budget list --resource-group sri-tesis-rg
```

O directo en el portal: https://portal.azure.com → "Cost Management + Billing".
