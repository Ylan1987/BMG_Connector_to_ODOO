# Registro de Cambios y Ajustes - GEMINI

Este archivo funciona como un registro histórico de las actualizaciones, scripts de mantenimiento y cambios de lógica implementados en el sistema BMG v2.0.

## Fecha: 03 de Julio de 2026

### 1. Mejoras en la Generación de Tapas (Script 07)
Se ajustó el posicionamiento y formato del código de barras que se inserta en las tapas de los libros para evitar problemas de guillotina y lectura:
*   **Reposicionamiento:** El código de barras se movió considerablemente más arriba para alejarlo del `TrimBox` inferior, eliminando el riesgo de que la guillotina de producción lo corte.
*   **Redimensionamiento y Proporción:** Se modificó la lógica para que el código mantenga obligatoriamente sus proporciones correctas (`keep_proportion=True`), evitando que se pixele o se estire, lo cual dificultaba la lectura con escáneres.
*   **Expansión Dinámica:** Se incorporó un sistema de seguridad que detecta si el canvas (PDF) de la tapa es muy ajustado. Si no hay espacio suficiente en el margen inferior, el script expande dinámicamente el `MediaBox` hacia arriba agregando espacio blanco de forma automática para asegurar que el código de barras entre sin superponerse a los diseños.

### 2. Activación de Producción (`PRODUCCION_ACTIVADA = True`)
Se preparó el terreno para encender oficialmente el orquestador en Odoo sin generar problemas retroactivos. Al activar la variable, los Scripts 4 y 5 empiezan a trabajar activamente con Odoo. Para que no procesen el historial completo:
*   **Congelamiento General (`congelar_pedidos_viejos.py`):** Se creó y ejecutó un script que marcó a todos los pedidos existentes en la base de datos local con el estado `'OF_CREADA'`. Esto le indica al Script 5 que los ignore (ya que asume que ya fueron fabricados en el pasado), evitando un aluvión de creaciones de Órdenes de Fabricación en Odoo.

### 3. Ajuste Quirúrgico: Descongelamiento de Pedidos en Curso
El congelamiento inicial (Punto 2) bloqueó la base de datos por completo, afectando también a los pedidos recientes que estaban "en espera" (Ej: estado *Pendiente de Archivos* en BMG).
*   **Descongelamiento Seguro (`descongelar_crudos.py`):** Se creó y corrió un segundo script en el servidor que evaluó toda la base de datos. Este script devolvió al estado `'PENDIENTE'` **únicamente** a los pedidos que aún no habían sido confirmados en Odoo (los que no tenían un `odoo_pickings_data_json` generado por el Script 4).
*   **Resultado Final:** Los pedidos verdaderamente viejos (más de 1400) se mantuvieron congelados e inofensivos. Los pedidos en curso (~137, incluyendo `PED00663395` y `PED00663397`) volvieron a la normalidad. Cuando estos pedidos avancen a "Muestra Aprobada" en BMG, el orquestador los confirmará en Odoo y les generará su OF normalmente.
