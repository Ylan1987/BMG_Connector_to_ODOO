# Cierre de pedidos BMG con OF y/o picking sin cerrar

Documentación de lo que se hizo el 30/07/2026 para limpiar pedidos BMG ya
terminados en la vida real, pero cuyo picking (entrega) y/o OF (orden de
fabricación) nunca se marcó como hecha en Odoo — y de cómo repetir el
proceso, porque va a volver a hacer falta mientras el equipo termina de
adoptar la costumbre de cerrar esos pasos.

## El problema

En Odoo, cerrar el picking (entrega física) y cerrar la OF (fabricación) son
dos acciones manuales separadas, independientes entre sí y de que el pedido
ya esté facturado. El personal de producción/depósito no siempre las marca a
tiempo — sobre todo la operación de **tapa** (el operario de interior
aprendió primero a marcar sus tareas como hechas; el de tapa fue quedando
atrás). Resultado: pedidos que ya se cobraron y ya se entregaron de verdad,
pero que en Odoo siguen "abiertos", y que en BMG pueden haber quedado con un
estado de producción viejo en vez de "Entregado".

## Cómo se buscan los pedidos candidatos (criterio de búsqueda)

Ver `auditar_pedidos_abiertos.py`. Es de **solo lectura**, no cambia nada.

1. **Universo BMG real**: líneas de venta (`sale.order.line`) con
   `x_bmg_order_line > 0`.

   ⚠️ **Ojo con el filtro**: la primera vez usamos `x_bmg_order_line != False`
   y trajo pedidos que NO son de BMG (ej. `P80906`, un pedido de etiquetas
   para NUTRIDIE). El campo es un entero que en Odoo tiene default `0` en
   *toda* línea de venta del sistema, y `0 != False` es verdadero a nivel de
   dominio ORM para un campo entero — o sea, ese filtro deja pasar
   prácticamente cualquier línea. El filtro correcto es `> 0`, porque un
   número de línea BMG real siempre es 1, 2, 3...

2. De esas líneas, sacamos los pedidos de venta (`sale.order`) distintos.

3. Nos quedamos con los que están **`invoice_status = 'invoiced'`** (facturados
   por el 100% del total).

4. De esos, buscamos los que tengan:
   - **`picking_ids`** con algún `stock.picking` que no esté en estado
     `done`/`cancel` ("solo picking abierto"), y/o
   - **OF sin cerrar**: cruzamos `sale.order.mrp_production_ids` con una
     búsqueda extra por `mrp.production.origin = nombre del pedido` (las OF
     "nietas" — por ejemplo el interior color de un componente — pueden
     haber quedado con un grupo de abastecimiento distinto al del pedido y
     no aparecer en el campo estándar).

Esto da tres grupos:
- **Solo picking abierto** (OF ya cerrada, falta validar la entrega).
- **Solo OF abierta** (picking ya validado, falta cerrar la fabricación).
- **Ambos abiertos**.

## Causas raíz encontradas (contexto, ya resueltas o en curso)

1. **Commit `65d3cac` (28/07/2026)** en este mismo repo rompió el filtro de
   estados que usan `script_06`/`script_07` para no generar tapa/interior de
   pedidos Anulados/Entregados/Facturados. Se arregló agregando esos IDs de
   vuelta a `ESTADOS_NO_CONFIRMABLES_PARA_OF` en `common/mapeos.py` (commit
   `38bbffb`, ya pusheado y con pull hecho en el servidor).

2. **Bug activo en el addon de Odoo** `nesta_bmg_factory_orders_status_reporting`
   (`models/mrp_workorder.py`): cada vez que un `mrp.workorder` pasa a
   `progress` o `done`, se encola automáticamente una notificación a BMG con
   el estado de ESA operación puntual (ej. "Tapa Impresa"), sin chequear si
   el pedido ya tiene un estado más avanzado en BMG (Entregado, Facturado).
   Si alguien cierra hoy una OF de tapa atrasada de un pedido que ya se
   entregó hace semanas, BMG recibe un **retroceso de estado**. Esto ya pasó
   de verdad (ver caso P80463 más abajo). **Este bug sigue sin arreglar** —
   es la razón por la que todo este proceso hay que hacerlo con cuidado
   (pausar la cola) y probablemente haya que repetirlo.

## Qué se cambia en Odoo vs qué se cambia en BMG

**En Odoo** (vía RPC, `odoorpc`, conectado a `prod17.odoo.imprentadiagonal.com.uy`):
- Se cierran las **OF** (`mrp.production` + sus `mrp.workorder`).
- Se valida el **picking** (`stock.picking.button_validate()`).
- Se borran entradas de la tabla `bmg.notification.queue` (la cola interna
  de Odoo hacia BMG) — solo las que generó este mismo proceso.

**En BMG** (vía SOAP, `BMBillingByOrder` / `BMBillingStatusChange`, las mismas
llamadas que usa `script_02` y el addon):
- Se consulta el estado real actual de cada línea.
- Si no está ya en Entregado/Facturado, se manda **Entregado** (ID 43 para
  POD, ID 204 para eDist — el tipo se determina con
  `sale_order.opportunity_id.x_order_type == 'eDistrib. 1 a 1'`).

## El proceso paso a paso (`cerrar_pedidos_bmg.py`)

Para cada pedido, en este orden exacto:

1. **Chequeo de seguridad**: si el pedido tiene algún picking abierto que
   NO sea la entrega BMG normal (`x_is_bmg_picking = False` — ej. una
   devolución `WH/IN`, ver caso P80450), **no se toca nada de ese pedido**.
   Se reporta aparte para revisión manual.

2. **Cerrar las OF**, en este orden obligatorio:
   **interior (color y/o ByN) → tapa → libro final.**
   Cerrar en otro orden puede fallar porque el libro necesita sus
   componentes ya producidos.
   Por cada OF: se termina cada `mrp.workorder` no cerrado
   (`button_start` + `button_finish`), se fija `qty_producing = product_qty`,
   y se llama `button_mark_done()`.

3. **Validar el picking BMG** con `button_validate()`.

4. **Limpiar la cola**: se borran de `bmg.notification.queue` (estado
   `pending`) solo las entradas cuyo `workorder_id` es alguno de los que
   tocamos en el paso 2, más las que se hayan creado para este
   `sale_order_id` desde que arrancó el proceso. **Nunca se toca nada más
   viejo ni de otro pedido** — así no se pisa notificaciones reales que haya
   generado otra persona trabajando en paralelo mientras corría el lote.

5. **Chequear y corregir BMG**: se consulta el estado real actual (no lo que
   nosotros mandamos antes) y si está atrasado se corrige a Entregado.

### El cron de notificaciones (`ir.cron` id 65, "BMG: Procesar Cola de Notificaciones")

Corre cada 1 minuto y manda lo que esté `pending` en la cola. **Mientras se
corre este proceso sobre una tanda de pedidos hay que tenerlo pausado**
(`active = False`), porque si no, lo que se encola en el paso 2 (estados de
producción intermedios, atrasados respecto a Entregado) puede salir disparado
hacia BMG antes de que el paso 4 lo limpie. Se reactiva al terminar la tanda.
No hay ventana segura para dejarlo prendido durante el proceso: manda cada 1
minuto, y cerrar varias OF con varios workorders cada una tarda más que eso.

## Casos especiales encontrados (y cómo se resolvieron)

- **Wizard "Consumption Warning" al cerrar la OF del libro final**: Odoo
  compara lo que la OF realmente consumió contra lo que la Lista de
  Materiales (LdM) dice *ahora* que debería consumir. Como `script_05`
  reescribe la misma LdM cada vez que entra un pedido nuevo que comparte esa
  variante de libro, para pedidos viejos el componente registrado ya no
  coincide con el que la LdM "actual" espera. Es solo un aviso de
  comparación, no un problema real — se confirma el wizard
  (`mrp.consumption.warning.action_confirm`) con los mismos datos que Odoo ya
  calculó. Manejado automáticamente en `cerrar_ofs()`.

- **Producto con ruta "Buy" en vez de "Fabricar"** (ej. producto 14649
  "Libros (copia)..."): la mayoría de las variantes genéricas de libro que
  crea V2.0 tienen la ruta mal puesta, y su stock queda permanentemente en
  `qty_available = 0` con `virtual_available` muy negativo (se vio un caso en
  -1901), aunque las OF que las producen se cierren bien. Esto hace que
  `button_validate()` del picking falle con *"No puede validar un traslado si
  no hay cantidades reservadas"*. Se resuelve forzando `quantity =
  product_uom_qty` en los `stock.move` del picking antes de reintentar
  validar — parámetro `forzar_cantidad=True` en `validar_pickings()`. Usar
  con criterio: se le está diciendo a Odoo que ese stock existió aunque el
  sistema no lo tenga registrado, confiando en que el libro se entregó de
  verdad.

- **Picking de devolución (`WH/IN`) mezclado con la entrega** — caso
  **P80450** (30/07/2026): tenía un `stock.picking` tipo *"Receipts"* de
  `Partner Locations/Customers → WH/Stock` (una devolución real, se vio
  `qty_delivered = -3` en una de las líneas — probablemente reimpresión de
  ejemplares dañados) además del `WH/OUT` normal. Ninguno de los dos estaba
  marcado `x_is_bmg_picking = True`. Este pedido quedó **sin resolver del
  todo**: se cerraron sus OF y se corrigió el estado en BMG, pero el
  `WH/OUT/20712` sigue sin validar porque no queríamos forzar una devolución
  sin entender qué pasó. Por eso el script frena automáticamente (sin tocar
  nada) cualquier pedido con un picking abierto que no sea
  `x_is_bmg_picking = True` — `verificar_pickings_no_bmg()` /
  `procesar_pedido_completo()` lo hacen antes de cualquier otra acción.

- **Retroceso de estado real y confirmado en BMG (P80463, 24/07/2026)**:
  se reconstruyó la secuencia exacta desde `bmg.notification.queue`:
  17:44 picking validado → Entregado (43) enviado bien → 20:28 alguien marca
  "Imprimir Tapa" como hecha en Odoo → se manda "Tapa Impresa" (49), pisando
  el Entregado. Confirma que el bug del hook (causa raíz #2) no es teórico.

- **Estados que BMG mueve por su cuenta** (eDist): para pedidos eDist, BMG
  puede mostrar "Enviado" sin que nuestra cola le haya mandado nunca ese
  estado — BMG maneja su propia logística de distribución "1 a 1" del otro
  lado. No es un error nuestro ni hay que "corregirlo" a la fuerza si no
  viene de un retroceso generado por nosotros.

## Dónde está el código

- `auditar_pedidos_abiertos.py` — solo lectura, encuentra los pedidos
  candidatos. Genera `auditoria_resultado.json` en esta carpeta.
- `cerrar_pedidos_bmg.py` — el proceso de cierre en sí. Se puede importar
  (`procesar_pedido_completo`, `procesar_lote`) o correr por línea de
  comandos: `python cerrar_pedidos_bmg.py P80450 P80451 ...`
- Ambos están en este repo (`V2.0/utilidades_cierre_pedidos_bmg/`), commiteados
  a git, así que sobreviven aunque se borre el scratchpad de una sesión.

Las credenciales de Odoo y BMG están hardcodeadas en los scripts (mismas que
usa el resto de V2.0 vía `common/mapeos.py` — el de BMG se toma de ahí
directamente; el de Odoo está repetido porque estos scripts corren standalone,
fuera del flujo del orquestador).

## Antes de correr esto de nuevo

1. Correr `auditar_pedidos_abiertos.py` para ver el panorama actual.
2. Revisar `verificar_pickings_no_bmg()` sobre la lista antes de procesar en
   lote — no asumir que todos son "normales" como P80450 nos enseñó.
3. Pausar el cron `id=65` en Odoo (Ajustes > Técnico > Automatización >
   Acciones Planificadas > "BMG: Procesar Cola de Notificaciones") antes de
   arrancar.
4. Correr `procesar_lote([...])` sobre los pedidos ya verificados.
5. Reactivar el cron al terminar.
6. Ojalá para la próxima ya no haga falta: si se llega a arreglar el hook de
   `mrp_workorder.py` (causa raíz #2, pendiente), este proceso se vuelve
   mucho menos riesgoso y probablemente no haga falta pausar el cron.
