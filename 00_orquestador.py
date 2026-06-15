import sys
import logging
from datetime import datetime

# --- Importación de Módulos Comunes y Scripts de Flujo ---
from common import db_conn, mapeos, meli_api
import script_01_sincronizar_pedidos_bmg as script_01
import script_02_actualizar_estados_bmg as script_02
import script_03_crear_ordenes_venta_odoo as script_03
import script_04_confirmar_ventas_y_crear_pickings as script_04
import script_05_crear_ordenes_fabricacion as script_05
import script_06_generar_interior_produccion as script_06
import script_07_generar_tapa_produccion as script_07
import script_08_sincronizar_estados_meli as script_08

def run_full_flow():
    """
    Ejecuta la secuencia completa de scripts para procesar pedidos.
    """
    # --- Inicializar DB ---
    # Se asegura de que la tabla 'trabajos' y todas sus columnas existan.
    db_conn.inicializar_db()
    # --------------------

    # --- Asegurar Token de Mercado Libre ---
    # Esto refresca el token si faltan menos de 30 min y lo sincroniza con Odoo.
    # Forzamos la sincronización para que Odoo siempre tenga el token más reciente.
    meli_api.obtener_access_token(forzar_sync_odoo=True)
    # --------------------------------------

    print(f"--- 🚀 INICIANDO FLUJO DE TRABAJO COMPLETO [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")
    
    print("\n--- [Paso 1: Procesar Pedidos Nuevos] ---")
    script_01.run() # Lee de la API de BMG y guarda en la DB local

    print("\n--- [Paso 2: Crear Oportunidades y Pedidos de Venta en Odoo] ---")
    script_03.run()

    print("\n--- [Paso 3: Actualizar Estados de Pedidos] ---")
    script_02.run() # Actualiza estados intermedios si es necesario

    print("\n--- [Paso 4: Confirmar Ventas y Crear Pickings en Odoo] ---")
    script_04.run()

    if mapeos.PROCESAR_PDF_ACTIVADO:
        print("\n--- [Paso 5: Generar Archivos de Producción (TAPA)] ---")
        script_07.run()

        print("\n--- [Paso 6: Generar Archivos de Producción (INTERIOR)] ---")
        script_06.run()
    else:
        print("\n--- [Paso 5 y 6: Generación de PDFs OMITIDA (Toggle desactivado)] ---")

    if mapeos.PRODUCCION_ACTIVADA:
        print("\n--- [Paso 7: Crear Órdenes de Fabricación en Odoo] ---")
        script_05.run()
    else:
        print("\n--- [Paso 7: Creación de Órdenes de Fabricación OMITIDA (Toggle desactivado)] ---")

    print("\n--- [Paso 8: Sincronizar Estados de Envío Mercado Libre] ---")
    script_08.run()

    print(f"\n--- ✅ FLUJO DE TRABAJO COMPLETO FINALIZADO [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ---")


def main():
    """
    Función principal del orquestador.
    Verifica los argumentos de la línea de comandos y ejecuta las acciones correspondientes.
    """
    # Acción de inicialización de la base de datos
    if '--inicializar-db' in sys.argv:
        print("--- Solicitud de inicialización de base de datos ---")
        db_conn.inicializar_db()
        print("--- Proceso de inicialización finalizado ---")
        return

    # Ejecución del flujo de trabajo estándar
    run_full_flow()


if __name__ == "__main__":
    main()
