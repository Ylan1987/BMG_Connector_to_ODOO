# -*- coding: utf-8 -*-
"""
Reset puntual: vuelve a PENDIENTE el estado de TAPA (solo tapa, no interior)
para un order_code especifico, asi Script 07 lo reprocesa con el fix del
CropBox/MediaBox aplicado.

Usa la MISMA ruta de DB que usa el sistema en vivo (mapeos.DB_FILE via
db_conn), no una ruta relativa suelta, para evitar tocar el archivo
equivocado.
"""
import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import mapeos

ORDER_CODE_BUSCAR = "664256"  # PED00664256
LINE_NUMBER = 1

db_path = os.path.abspath(mapeos.DB_FILE)
print(f"Conectando a la DB real del sistema: {db_path}")

conn = sqlite3.connect(mapeos.DB_FILE)
cursor = conn.cursor()

cursor.execute(
    "SELECT order_code, line_number, estado_tapa_produccion FROM trabajos "
    "WHERE order_code LIKE ? AND line_number = ?",
    (f"%{ORDER_CODE_BUSCAR}%", LINE_NUMBER)
)
rows = cursor.fetchall()

if not rows:
    print(f"⚠️ No se encontro ningun trabajo con order_code like '%{ORDER_CODE_BUSCAR}%' y line_number={LINE_NUMBER}")
else:
    for row in rows:
        print(f"Encontrado: order_code={row[0]} line_number={row[1]} estado_tapa_produccion actual={row[2]}")

    cursor.execute(
        "UPDATE trabajos SET estado_tapa_produccion = ? "
        "WHERE order_code LIKE ? AND line_number = ?",
        (mapeos.LOCAL_DB_STATUS_TAPA_PENDIENTE, f"%{ORDER_CODE_BUSCAR}%", LINE_NUMBER)
    )
    conn.commit()
    print(f"✅ Reseteado a '{mapeos.LOCAL_DB_STATUS_TAPA_PENDIENTE}'. Filas afectadas: {cursor.rowcount}")

conn.close()
