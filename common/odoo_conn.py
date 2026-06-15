import odoorpc
# Importamos las constantes desde el archivo de mapeos en la misma carpeta
from . import mapeos

def conectar_odoo():
    """Se conecta a la API de Odoo y devuelve el objeto de la API."""
    try:
        # Usamos las variables importadas desde el módulo de mapeos
        odoo = odoorpc.ODOO(
            mapeos.ODOO_URL,
            protocol='jsonrpc+ssl',
            port=443,
            timeout=120
        )
        odoo.login(
            mapeos.ODOO_DB,
            login=mapeos.ODOO_USUARIO,
            password=mapeos.ODOO_CONTRASENA
        )
        print("✅ Conexión a Odoo establecida con éxito.")
        return odoo
    except Exception as e:
        print(f"❌ Error crítico al conectar con Odoo: {e}")
        return None
