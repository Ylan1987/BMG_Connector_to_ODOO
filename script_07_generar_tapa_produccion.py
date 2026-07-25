import os
import re
import sqlite3
import fitz
import logging
from common import mapeos, db_conn, odoo_conn

# Configurar logging
_logger = logging.getLogger(__name__)

MM_PER_POINT = 25.4 / 72.0
BLEED_PTS = 3 / MM_PER_POINT

def limpiar_id(id_original, prefijo):
    if not id_original: return None
    id_sin_prefijo = id_original[len(prefijo):] if id_original.startswith(prefijo) else id_original
    return id_sin_prefijo.lstrip('0')

def obtener_cajas_normalizadas_pypdf(ruta_archivo):
    import pypdf
    try:
        with open(ruta_archivo, 'rb') as file:
            reader = pypdf.PdfReader(file)
            page = reader.pages[0]
            media = page.mediabox
            trim = page.get('/TrimBox') or media
            tx, ty = -float(media[0]), -float(media[1])
            return {
                'media': fitz.Rect(float(media[0])+tx, float(media[1])+ty, float(media[2])+tx, float(media[3])+ty),
                'trim': fitz.Rect(float(trim[0])+tx, float(trim[1])+ty, float(trim[2])+tx, float(trim[3])+ty)
            }
    except: return None

def encontrar_ruta_trabajo_dinamicamente(base_path, publisher_ids_limpios, title_id_limpio):
    pub_ids = []
    for pid in publisher_ids_limpios:
        if not pid: continue
        for p in str(pid).split(','):
            clean_p = p.replace('EDIT', '').strip().lstrip('0')
            if clean_p and clean_p not in pub_ids: pub_ids.append(clean_p)
    tid = str(title_id_limpio).replace('PAP', '').strip().lstrip('0')
    
    _logger.info(f"      -> Buscando ruta para TitleID: '{tid}' con Publisher IDs: {pub_ids}")
    _logger.info(f"      -> RUTA BASE A REVISAR: {base_path}")

    if not os.path.exists(base_path):
        _logger.warning(f"      -> ❌ Ruta base no encontrada: {base_path}")
        return None
    
    try:
        # Structure: base_path / Pais / Facility / Publisher / Title
        for pais_dir in os.listdir(base_path):
            pais_path = os.path.join(base_path, pais_dir)
            if not os.path.isdir(pais_path): continue
            
            _logger.info(f"      -> Revisando País: {pais_path}")
            for facility_dir in os.listdir(pais_path):
                facility_path = os.path.join(pais_path, facility_dir)
                if not os.path.isdir(facility_path): continue
                
                for pub_dir in os.listdir(facility_path):
                    current_pub_id = pub_dir.lstrip('0')
                    current_pub_id = pub_dir.lstrip('0').strip()
                    if current_pub_id in pub_ids:
                        pub_path = os.path.join(facility_path, pub_dir)
                        if not os.path.isdir(pub_path): continue

                        _logger.info(f"      -> Match de Publisher encontrado. Revisando carpeta: {pub_path}")
                        for title_dir in os.listdir(pub_path):
                            if title_dir.lstrip('0') == tid:
                                ruta = os.path.join(pub_path, title_dir)
                                _logger.info(f"      -> ✅ Carpeta encontrada: {ruta}")
                                return ruta
    except Exception as e:
        _logger.error(f"      -> ❌ Error buscando ruta dinámicamente: {e}")
        pass
    
    _logger.warning(f"      -> ⚠️ No se encontró la carpeta para TitleID: {tid} con los publishers provistos.")
    return None

def encontrar_archivo_mas_reciente(directorio, title_id_limpio, tipo_archivo, order_type):
    archivos_aptos = []; archivos_coherencia = []; archivos_totales = []
    es_edist = order_type == 'eDistrib. 1 a 1'
    PATRON_MASTER = r"MASTER"; PATRON_TAPA = r"(COVER|TAPA)"; PATRON_TAPA_GEN = r"(COVER|TAPA)"
    
    patron_apto_pod = re.compile(f"^{re.escape(title_id_limpio)}_TAPA.*_(\\d+)\\.pdf$", re.IGNORECASE)
    patron_master_tipo = re.compile(PATRON_TAPA, re.IGNORECASE)
    patron_tipo_gen = re.compile(PATRON_TAPA_GEN, re.IGNORECASE)
    patron_exclusion = re.compile(r"(IMPO)", re.IGNORECASE)

    try:
        for f in os.listdir(directorio):
            ruta = os.path.join(directorio, f)
            try: mtime = os.path.getmtime(ruta)
            except: continue
            if not es_edist and patron_tipo_gen.search(f) and not patron_exclusion.search(f):
                archivos_totales.append({'fecha': mtime, 'ruta': ruta, 'nombre': f})
            
            is_master = re.search(PATRON_MASTER, f, re.IGNORECASE)
            match_pod = patron_apto_pod.match(f)
            if es_edist and is_master and patron_master_tipo.search(f):
                archivos_coherencia.append({'fecha': mtime, 'ruta': ruta, 'nombre': f})
            elif not es_edist and match_pod:
                archivos_aptos.append({'version': int(match_pod.group(1)), 'fecha': mtime, 'ruta': ruta, 'nombre': f})

        if es_edist:
            if not archivos_coherencia: return None, "No se encontró un archivo MASTER de tapa."
            mejor = max(archivos_coherencia, key=lambda x: x['fecha'])
            return mejor['ruta'], None
        else:
            if not archivos_aptos: return None, "No se encontró un archivo validado (*_TAPA_..._X.pdf)."
            mejor = max(archivos_aptos, key=lambda x: (x['fecha'], x['version']))
            if archivos_totales:
                posterior = max(archivos_totales, key=lambda x: x['fecha'])
                if posterior['fecha'] > mejor['fecha']:
                    msg = f"Se encontró un archivo posterior al validado: `{posterior['nombre']}`. Por favor, corregir el error en el NAS para procesar el validado que tenga la fecha más reciente."
                    return None, msg
            return mejor['ruta'], None
    except: return None, "Error al listar el directorio en el NAS."

def procesar_tapa(trabajo_actual):
    oc = trabajo_actual.get('order_code')
    ln = trabajo_actual.get('line_number')
    tid = trabajo_actual.get('title_id')
    print(f"    Procesando TAPA -> Pedido: {oc} | Línea: {ln} | TitleID: {tid}")
    ruta_orig = trabajo_actual['ruta_archivo_tapa_original']
    doc = None
    ruta_tmp_agrandado = None
    try:
        cajas = obtener_cajas_normalizadas_pypdf(ruta_orig)
        if not cajas:
            return None
        trim = cajas['trim']

        # Cuanto espacio necesita REALMENTE el codigo de barras (mas su margen)
        # arriba del trim. Un solo lugar para estos numeros: se usan tanto para
        # decidir si hace falta agrandar el lienzo como, mas abajo, para ubicar
        # el codigo de barras y el texto de laminado.
        MARGEN_SOBRE_TRIM_PT = 3 / MM_PER_POINT  # 3mm de separacion sobre el trim
        ALTO_BARCODE_PT = 60
        espacio_necesario = MARGEN_SOBRE_TRIM_PT + ALTO_BARCODE_PT

        # Lectura liviana de los boxes originales (solo para decidir si hace falta
        # agrandar el lienzo; no se escribe nada todavia).
        doc_lectura = fitz.open(ruta_orig)
        media = doc_lectura[0].mediabox
        cropbox_actual = doc_lectura[0].cropbox
        doc_lectura.close()

        # --- Agrandar el lienzo (MediaBox) de forma centrada si no hay espacio arriba del trim ---
        # Todo lo que insertamos (codigo de barras + leyenda de laminado) va
        # SIEMPRE arriba del trim, nunca abajo - asi que solo el margen de
        # ARRIBA decide si hace falta agrandar. Si ya alcanza, no se toca nada.
        espacio_arriba = media.y1 - trim.y1

        ruta_para_fitz = ruta_orig
        if espacio_arriba < espacio_necesario:
            # Centrado: agrandamos lo mismo arriba que abajo (el doble de alto total
            # que si solo creciera de un lado), en vez de crecer de un solo lado.
            falta = espacio_necesario - espacio_arriba
            nuevo_bottom = media.y0 - falta
            nuevo_top = media.y1 + falta
            # IMPORTANTE: no asumimos que el CropBox original coincide con el
            # MediaBox original. Si el PDF trae un CropBox propio (distinto),
            # asignar directamente 'nuevo_media' como CropBox puede fallar con
            # 'CropBox not in MediaBox' si ese CropBox original queda afuera.
            # Tomamos la UNION de: MediaBox actual, CropBox actual, y el nuevo
            # alto necesario. Al asignar esa misma union a ambos (Media y Crop),
            # el CropBox por construccion siempre queda contenido.
            union = fitz.Rect(
                min(media.x0, cropbox_actual.x0),
                min(nuevo_bottom, media.y0, cropbox_actual.y0),
                max(media.x1, cropbox_actual.x1),
                max(nuevo_top, media.y1, cropbox_actual.y1),
            )
            _logger.info(f"      [DEBUG] TitleID {trabajo_actual.get('title_id')}: "
                         f"media_orig={media!r} cropbox_orig={cropbox_actual!r} -> union={union!r}")
            # IMPORTANTE: agrandamos los boxes con pypdf, NO con set_mediabox()+
            # set_cropbox() de PyMuPDF. Para paginas cuyo MediaBox original tiene
            # origen no-cero (comun en estos archivos: x0/y0 negativos),
            # set_cropbox() de fitz revienta con "CropBox not in MediaBox" pase lo
            # que pase - confirmado a mano: falla con margenes de 0.5pt Y de 22pt,
            # y hasta pasandole el MISMO rect que el MediaBox recien seteado. No es
            # un tema de redondeo de punto flotante (la vieja hipotesis): page.cropbox
            # de PyMuPDF en esta version reporta las coordenadas en el frame
            # "display" (0,0), mientras que set_cropbox() valida contra el frame
            # crudo del MediaBox - dos sistemas de coordenadas que no coinciden
            # cuando el MediaBox no arranca en (0,0).
            # pypdf (la misma libreria que ya usamos arriba para leer los boxes con
            # confianza) no tiene ese problema: sus setters .mediabox/.cropbox
            # escriben directo el valor pedido. Dejamos que pypdf arme un archivo
            # intermedio ya con el lienzo correcto, y fitz recien entra despues,
            # solo para insertar texto y codigo de barras - nunca toca boxes.
            import pypdf
            from pypdf.generic import RectangleObject
            EPS = 0.5
            crop = fitz.Rect(union.x0 + EPS, union.y0 + EPS, union.x1 - EPS, union.y1 - EPS)
            reader = pypdf.PdfReader(ruta_orig)
            writer = pypdf.PdfWriter()
            writer.append(reader)
            page_pypdf = writer.pages[0]
            page_pypdf.mediabox = RectangleObject((union.x0, union.y0, union.x1, union.y1))
            page_pypdf.cropbox = RectangleObject((crop.x0, crop.y0, crop.x1, crop.y1))
            ruta_tmp_agrandado = ruta_orig + f".agrandado_{oc}_{ln}.tmp.pdf"
            with open(ruta_tmp_agrandado, 'wb') as f:
                writer.write(f)
            ruta_para_fitz = ruta_tmp_agrandado
        # ---------------------------------------------------------------------

        doc = fitz.open(ruta_para_fitz)

        laminado = trabajo_actual.get('laminate')

        # IMPORTANTE: 'trim' viene de pypdf en el frame CRUDO del PDF (origen abajo-
        # izquierda, Y crece hacia ARRIBA), normalizado solo restando el origen del
        # MediaBox ORIGINAL (media.x0/media.y0). insert_text()/insert_image() de
        # fitz, en cambio, ubican en el frame de PAGINA (origen arriba-izquierda,
        # Y crece hacia ABAJO) - el mismo que reporta page.rect. Usar 'trim.y1'
        # directo como Y de fitz (como se hacia antes) pega el texto/codigo de
        # barras contra el borde SUPERIOR de la hoja, en vez de justo arriba del
        # trim. Conversion: fitz_y = borde_superior_pagina_actual - y_crudo.
        media_final_y1 = union.y1 if ruta_tmp_agrandado else media.y1
        trim_y1_crudo = trim.y1 + media.y0  # revertir la normalizacion de pypdf
        y_base = media_final_y1 - trim_y1_crudo - MARGEN_SOBRE_TRIM_PT

        if laminado:
            doc[0].insert_text(fitz.Point(trim.x0, y_base), f"Laminado: {laminado}", fontsize=10)

        base_barcode = trabajo_actual.get('odoo_sale_order_name') or trabajo_actual.get('order_code')
        barcode_text = f"{base_barcode}-{trabajo_actual.get('line_number')}" if base_barcode else None
        if barcode_text:
            try:
                import io
                from barcode import Code128
                from barcode.writer import ImageWriter
                buffer = io.BytesIO()
                Code128(barcode_text, writer=ImageWriter()).write(buffer, options={'write_text': False})

                # Apilado hacia arriba desde la misma linea base que el texto de
                # laminado (y_base): en el frame de fitz "hacia arriba" es Y mas
                # chico, por eso y_top = y_bottom - 60.
                y_bottom = y_base
                y_top = y_bottom - ALTO_BARCODE_PT
                barcode_rect = fitz.Rect(trim.x0 + 150, y_top, trim.x0 + 150 + 500, y_bottom)
                doc[0].insert_image(barcode_rect, stream=buffer.getvalue(), keep_proportion=True)
            except Exception as e:
                print(f"      ADVERTENCIA: No se pudo insertar el código de barras en la tapa. Error: {e}")
        
        fw, fh = (trim.width + 2*BLEED_PTS)*MM_PER_POINT, (trim.height + 2*BLEED_PTS)*MM_PER_POINT
        ps = ""
        if (fw<=320 and fh<=350) or (fh<=320 and fw<=350): ps = "33x36"
        elif (fw<=320 and fh<=470) or (fh<=320 and fw<=470): ps = "33x48.7"
        elif (fw<=320 and fh<=690) or (fh<=320 and fw<=690): ps = "33x70"
        else: 
            doc.close()
            return None

        oc = limpiar_id(trabajo_actual['order_code'], 'PED')
        tit = re.sub(r'[\\/*?:"<>|]', "", trabajo_actual['title'])[:50]
        nom = f"{oc}-{trabajo_actual['line_number']}_{ps}x{trabajo_actual['quantity_requested']}_{tit}.pdf"
        ruta_f = os.path.join(mapeos.DEST_PATH_TAPAS, nom)
        doc.save(ruta_f)
        doc.close()
        return ruta_f, ps
    except Exception as e:
        print(f"      ERROR procesando tapa: {e}")
        if doc: doc.close()
        return None
    finally:
        if ruta_tmp_agrandado and os.path.exists(ruta_tmp_agrandado):
            try: os.remove(ruta_tmp_agrandado)
            except Exception: pass

def run():
    if not mapeos.PROCESAR_PDF_ACTIVADO: return
    print("--- Script 7 (TAPA) ---")
    
    conn = None
    trabajos = []
    try:
        conn = db_conn.conectar_db()
        if conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' for _ in mapeos.ESTADOS_A_EXCLUIR_PRODUCCION)
            query = f"SELECT * FROM trabajos WHERE odoo_pickings_data_json IS NOT NULL AND estado_tapa_produccion = ? AND (line_status_id IS NULL OR line_status_id NOT IN ({placeholders}))"
            
            params = [mapeos.LOCAL_DB_STATUS_TAPA_PENDIENTE] + mapeos.ESTADOS_A_EXCLUIR_PRODUCCION
            cursor.execute(query, params)
            
            trabajos = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"ERROR en Script 7 al consultar la base de datos: {e}")
    finally:
        if conn:
            conn.close()

    if not trabajos:
        return

    odoo_api = odoo_conn.conectar_odoo() if trabajos else None

    for t in trabajos:
        rt = t.get('ruta_trabajo')
        tid = limpiar_id(t.get('title_id', ''), 'PAP')
        if not rt:
            pids = [t.get('publisher_id'), t.get('publisher_facility')]
            rt = encontrar_ruta_trabajo_dinamicamente(mapeos.BASE_STORAGE_PATH, [p for p in pids if p], tid)
            if rt:
                conn = db_conn.conectar_db(); cursor = conn.cursor()
                cursor.execute("UPDATE trabajos SET ruta_trabajo = ? WHERE order_code = ? AND line_number = ?", (rt, t['order_code'], t['line_number']))
                conn.commit(); conn.close()

        if rt:
            r_orig, error_msg = encontrar_archivo_mas_reciente(rt, tid, 'TAPA', t.get('order_type', ''))
            if r_orig:
                t['ruta_archivo_tapa_original'] = r_orig
                res = procesar_tapa(t)
                if res:
                    ruta_f, ps = res
                    conn = db_conn.conectar_db(); cursor = conn.cursor()
                    cursor.execute("UPDATE trabajos SET estado_tapa_produccion = 'GENERADO', ruta_archivo_tapa = ?, papel_tapa_size = ? WHERE order_code = ? AND line_number = ?", 
                                   (ruta_f, ps, t['order_code'], t['line_number']))
                    conn.commit(); conn.close()
                    print(f"  ✅ Tapa {t['order_code']} OK")
                    
                    # --- NOTIFICAR A ODOO ---
                    try:
                        if odoo_api and t.get('odoo_sale_order_id'):
                            so = odoo_api.env['sale.order'].browse(t['odoo_sale_order_id'])
                            so.message_post(body=f"✅ **Producción Tapa:** Generada correctamente.\nArchivo: `{os.path.basename(ruta_f)}`")
                    except: pass
                else:
                    # Marcar como error en la DB para no trabar el loop
                    conn = db_conn.conectar_db(); cursor = conn.cursor()
                    cursor.execute("UPDATE trabajos SET estado_tapa_produccion = 'ERROR' WHERE order_code = ? AND line_number = ?", 
                                   (t['order_code'], t['line_number']))
                    conn.commit(); conn.close()
                    print(f"  ❌ Error al procesar Tapa {t['order_code']}")
                    try:
                        if odoo_api and t.get('odoo_sale_order_id'):
                            so = odoo_api.env['sale.order'].browse(t['odoo_sale_order_id'])
                            body = f"⚠️ **Producción Tapa:** Error al procesar archivo físico (medidas incorrectas o archivo dañado).\nTitleID: {tid}"
                            so.message_post(body=body)
                    except: pass
            else:
                # Notificar fallo detallado (no se encontró archivo apto, se mantiene en PENDIENTE)
                try:
                    if odoo_api and t.get('odoo_sale_order_id'):
                        so = odoo_api.env['sale.order'].browse(t['odoo_sale_order_id'])
                        body = f"⚠️ **Producción Tapa:** {error_msg}\nTitleID: {tid}"
                        so.message_post(body=body)
                except: pass

if __name__ == "__main__":
    run()
