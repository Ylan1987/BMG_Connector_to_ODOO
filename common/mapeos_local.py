# -*- coding: utf-8 -*-
"""
Archivo de configuración LOCAL.
Los valores aquí sobreescriben a los de mapeos.py
"""

# Apuntar a la base de datos en el directorio raíz del proyecto
DB_FILE = 'trabajos.db'

# --- CONFIGURACIÓN DE ODOO (Producción) ---
# Completa estos valores con los datos de tu servidor de producción.
ODOO_URL = 'testkrl.odoo.imprentadiagonal.com.uy'
ODOO_DB = 'odoo17_prod'
ODOO_USUARIO = 'ylan.archimowicz@imprentadiagonal.com.uy'
#Para prod
ODOO_CONTRASENA = '9a50ca725dd8c0e451e8005982589dcdf3bf8fe7'
#Para test
#ODOO_CONTRASENA = '77436602dbb10c3959d3cf28e12e0cf4d253f667'

BASE_STORAGE_PATH = r'Z:\\'
DEST_PATH_TAPAS = r'C:\\Users\\ylana\\Downloads\\Trabajos\\LAD\\Tapas'
DEST_PATH_INTERIOR = r'C:\\Users\\ylana\\Downloads\\Trabajos\\LAD\\Interior'
BMG_TITLE_ID_PREFIX = 'PAP'

# --- CONFIGURACIÓN DE MERCADO LIBRE ---
MELI_ACCESS_TOKEN = "APP_USR-2304119893923185-051921-dc9e0b8737194bb0eb3735394033e65b-431632699"
MELI_REFRESH_TOKEN = "TG-6a0d0ee6fb14810001e58260-431632699"
ML_SINCRO_ACTIVADA = True