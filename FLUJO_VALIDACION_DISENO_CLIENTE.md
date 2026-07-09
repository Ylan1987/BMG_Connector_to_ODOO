# Flujo de Validación del Diseño del Cliente

Documenta cómo funciona hoy (2026-07-09) el circuito de "Validación de
diseños del cliente": desde que se confirma el pedido hasta que arranca la
producción física. Involucra 3 sistemas: BMG (API SOAP), el conector V2.0
(este proyecto) y Odoo (CRM + Proyecto).

## Resumen de la dirección del flujo

```
BMG (SOAP) ──[script_02, polling periódico]──► DB local V2.0 ──► Odoo (CRM + Project)
                                                                        │
Odoo (cambio de etapa, manual o automático) ──[bmg.notification.queue]──► BMG (SOAP)
```

- **BMG → Odoo**: lo hace `script_02_actualizar_estados_bmg.py` (este
  proyecto), consultando `BMBillingByOrder` por cada pedido activo.
- **Odoo → BMG**: se resuelve enteramente del lado de Odoo, con el modelo
  `bmg.notification.queue` (módulo `nesta_bmg_factory_orders_status_reporting`
  en el repo `odoo-nesta`), que un cron procesa y llama a
  `BMBillingStatusChange` de BMG.

## 0. Disparador inicial: se crea la tarea de validación

Cuando `script_03_crear_ordenes_venta_odoo.py` crea el Pedido de Venta y el
pedido es `order_type == '1ra. impr. std'` + `publisher_facility == LAD` +
`mapeos.PRODUCCION_ACTIVADA`, se agrega una línea de producto
**"Validación de diseños del cliente"** (script_03, línea ~454).

Ese producto está configurado en Odoo para autogenerar una tarea en el
proyecto **`[Pre-Producción] Validación del Diseño del cliente`** al
confirmarse la venta (integración estándar de Odoo `sale_project`).
`script_04_confirmar_ventas_y_crear_pickings.py` (línea ~440) encuentra esa
tarea recién creada, la renombra a `Validación Diseño - {order_code}-{line}`,
le graba el campo `x_bmg_order_line`, y guarda el `project_task_id` en la
tabla local `trabajos` (columna `odoo_project_task_id`) para referencia
futura.

## 1. Etapas de la tarea (proyecto id 3 en Odoo, orden real por `sequence`)

```
Conseguir Archivos o datos → Para Validar → Para enviar consultas al cliente
  → Para Enviar muestra → Esperando respuesta → Planificar producción → (archivada)
```

(Confirmado consultando directo `project.task.type` filtrado por
`project_ids` del proyecto - no asumir el orden solo por el código.)

## 2. Qué mueve la tarjeta SOLA (automático, reaccionando a BMG)

Todo esto lo hace `script_02_actualizar_estados_bmg.py` cuando, al
consultar `BMBillingByOrder`, detecta que el `LineStatusId` de BMG cambió
para esa línea. **Ningún operario nuestro tiene que tocar nada en BMG** para
que esto pase — lo dispara el propio sistema de BMG (por ejemplo, cuando el
CLIENTE sube sus archivos por el portal web de BMG).

| BMG dice... (LineStatusId) | Odoo hace... |
|---|---|
| PENDIENTE DE ORIGINAL (4) | Si la tarea ya existe → tarea a **"Conseguir Archivos o datos"** |
| ARCHIVOS RECIBIDOS WEB (5) | Tarea → **"Para Validar"** + avisa a BMG "EN VALIDACIÓN" (9) |
| MUESTRA RECHAZADA (15) | Tarea → vuelve a **"Conseguir Archivos o datos"** + avisa a BMG "PENDIENTE DE ORIGINAL" (4) (se reinicia el ciclo) |
| MUESTRA APROBADA (14) | Tarea → **"Planificar producción"** + avisa a BMG "IMPOSICIÓN PENDIENTE" (16) |

Además (no mueve la tarea, pero es parte del mismo flujo, sobre la
Oportunidad/CRM):

| BMG dice... | Odoo hace... |
|---|---|
| PRESUPUESTO ENVIADO (2) | Oportunidad → etapa "Esperando Respuesta" + actividad "Contactar cliente para cerrar venta" |
| PENDIENTE DE ORIGINAL (4) | Oportunidad → "Ganado sin OT"; marca hecha la actividad de contactar cliente; crea actividad "Reclamar archivos" |
| ARCHIVOS RECIBIDOS WEB (5) | Oportunidad → "Ganado con OT"; marca hecha "Reclamar archivos" |
| ANULADO (38 POD / 234 eDist) | Cancela el Pedido de Venta en Odoo (`action_cancel`) |

## 3. Qué mueve una PERSONA a mano en el Kanban de Odoo

Con la tarea ya sentada en **"Para Validar"** (llegó ahí sola, ver punto 2),
una persona de nuestro lado:

1. Abre los archivos que subió el cliente y los revisa.
2. Si hace falta preguntarle algo al cliente antes de seguir, la pasa a
   **"Para enviar consultas al cliente"** — etapa puramente organizativa,
   no dispara nada hacia BMG.
3. Cuando está lista para mandarle una muestra digital al cliente, la pasa
   por **"Para Enviar muestra"** (tampoco dispara nada) y finalmente a
   **"Esperando respuesta"**.
4. **Este último movimiento (a "Esperando respuesta") SÍ dispara código**
   (`project_task.py`, `write()` override, en `odoo-nesta`): avisa
   automáticamente a BMG "MUESTRA DIGITAL" (10) — o sea "ya le mandamos la
   muestra al cliente, estamos esperando que la apruebe o rechace".

La aprobación/rechazo de esa muestra la decide BMG (o el cliente a través
del portal de BMG) y vuelve como MUESTRA APROBADA/RECHAZADA — punto 2 de
arriba, cerrando el círculo (puede repetirse varias veces si se rechaza).

## 4. Fin de la validación → arranca producción física

Cuando la tarea está en **"Planificar producción"** y alguien la
**archiva** (dando por hecho que ya se armó la Orden de Fabricación, vía
`script_05_crear_ordenes_fabricacion.py`), eso dispara automático
(`project_task.py`) el aviso a BMG de **"Producción coordinada" (19)**.

Ahí termina la validación y arranca el seguimiento de producción física, que
es un mapeo de estados totalmente distinto (códigos 20 a 108 en
`bmg_estados_mapeo.py`, disparados por cambios de estado en
`mrp.workorder`, no por el proyecto de validación) — fuera del alcance de
este documento.

## 5. Resumen: qué es automático y qué es manual

| Transición | ¿Quién la dispara? |
|---|---|
| Entrar a "Conseguir Archivos o datos" (primera vez) | Automático (BMG: PENDIENTE DE ORIGINAL) |
| Entrar a "Para Validar" | Automático (BMG: ARCHIVOS RECIBIDOS WEB) |
| "Para Validar" → "Para enviar consultas al cliente" | Manual |
| → "Para Enviar muestra" | Manual |
| → "Esperando respuesta" | Manual (mover la tarjeta) — **dispara aviso a BMG** |
| Rechazo → vuelve a "Conseguir Archivos o datos" | Automático (BMG: MUESTRA RECHAZADA) |
| Aprobación → "Planificar producción" | Automático (BMG: MUESTRA APROBADA) |
| Archivar desde "Planificar producción" | Manual (archivar la tarjeta) — **dispara aviso a BMG** |

## 6. Dónde está cada cosa (referencia rápida)

| Qué | Archivo |
|---|---|
| Nombres de etapas/actividades (constantes) | `common/mapeos.py` (`TASK_STAGE_*`, `OPPORTUNITY_STAGE_*`, `ACTIVITY_SUMMARY_*`) |
| Catálogo completo de IDs de estado BMG | `common/bmg_estados_mapeo.py` (`BMG_STATUS_MAP`) — también tiene el mapeo de producción física (códigos 59-108), fase posterior y separada de esta validación |
| Polling BMG → acciones en Odoo | `script_02_actualizar_estados_bmg.py` |
| Creación de la línea/tarea de validación | `script_03_crear_ordenes_venta_odoo.py` (línea ~454) crea la línea; `script_04_confirmar_ventas_y_crear_pickings.py` (línea ~440) renombra la tarea y setea `x_bmg_order_line` |
| Reacción a cambios manuales de etapa en Odoo | `odoo-nesta/nesta_bmg_factory_orders_status_reporting/models/project_task.py` |
| Cola y envío real a BMG (SOAP `BMBillingStatusChange`) | `odoo-nesta/nesta_bmg_factory_orders_status_reporting/models/bmg_notification_queue.py` |
