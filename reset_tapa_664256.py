# -*- coding: utf-8 -*-
"""
Reset puntual: vuelve a PENDIENTE el estado de TAPA (solo tapa, no interior)
para order_codes especificos, asi Script 07 los reprocesa con el fix real de
'CropBox not in MediaBox' aplicado (set_cropbox debe usar page.rect, no el
rect crudo pasado a set_mediabox).

Usa la MISMA ruta de DB que usa el sistema en vivo (mapeos.DB_FILE via
db_conn), no una ruta relativa suelta, para evitar tocar el archivo
equivocado.
"""
import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import mapeos

# Pedidos/lineas que siguieron fallando con CropBox/MediaBox incluso con el
# fix de set_cropbox(doc[0].rect) (ver log 2026-07-08 20:52) - necesitan el
# fix definitivo del margen epsilon para reprocesarse bien.
ORDER_LINES_BUSCAR = [
    ("664266", 2),
    ("664356", 1),
    ("664480", 1),
]

db_path = os.path.abspath(mapeos.DB_FILE)
print(f"Conectando a la DB real del sistema: {db_path}")

conn = sqlite3.connect(mapeos.DB_FILE)
cursor = conn.cursor()

for order_code_buscar, line_number in ORDER_LINES_BUSCAR:
    cursor.execute(
        "SELECT order_code, line_number, estado_tapa_produccion FROM trabajos "
        "WHERE order_code LIKE ? AND line_number = ?",
        (f"%{order_code_buscar}%", line_number)
    )
    rows = cursor.fetchall()

    if not rows:
        print(f"⚠️ No se encontro ningun trabajo con order_code like '%{order_code_buscar}%' y line_number={line_number}")
        continue

    for row in rows:
        print(f"Encontrado: order_code={row[0]} line_number={row[1]} estado_tapa_produccion actual={row[2]}")

    cursor.execute(
        "UPDATE trabajos SET estado_tapa_produccion = ? "
        "WHERE order_code LIKE ? AND line_number = ?",
        (mapeos.LOCAL_DB_STATUS_TAPA_PENDIENTE, f"%{order_code_buscar}%", line_number)
    )
    conn.commit()
    print(f"✅ Reseteado a '{mapeos.LOCAL_DB_STATUS_TAPA_PENDIENTE}'. Filas afectadas: {cursor.rowcount}")

conn.close()
