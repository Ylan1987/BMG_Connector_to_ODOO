import os
import re
import sqlite3
import fitz
import math
import json
from common import mapeos, db_conn, odoo_conn

MM_PER_POINT = 25.4 / 72.0
BLEED_PTS = 3 / MM_PER_POINT

# --- FONT CONFIGURATION FOR WORK ORDER ---
FONT_REGULAR_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

if not os.path.exists(FONT_REGULAR_PATH) or not os.path.exists(FONT_BOLD_PATH):
    if os.name == 'nt': # Windows
        FONT_REGULAR_PATH = "C:/Windows/Fonts/arial.ttf"
        FONT_BOLD_PATH = "C:/Windows/Fonts/arialbd.ttf"

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
            trim = page.get('/TrimBox')
            bleed = page.get('/BleedBox')
            
            tx, ty = -float(media[0]), -float(media[1])
            
            res = {
                'media': fitz.Rect(float(media[0])+tx, float(media[1])+ty, float(media[2])+tx, float(media[3])+ty)
            }
            if trim:
                res['trim'] = fitz.Rect(float(trim[0])+tx, float(trim[1])+ty, float(trim[2])+tx, float(trim[3])+ty)
            if bleed:
                res['bleed'] = fitz.Rect(float(bleed[0])+tx, float(bleed[1])+ty, float(bleed[2])+tx, float(bleed[3])+ty)
            
            return res
    except: return None

def encontrar_archivo_mas_reciente(directorio, title_id_limpio, tipo_archivo, order_type):
    archivos_aptos = []; archivos_coherencia = []; archivos_totales = []
    es_edist = order_type == 'eDistrib. 1 a 1'
    
    PATRON_MASTER = r"MASTER"; PATRON_CONTENIDO = r"(CONTENT|CONTENIDO|INTERIOR)"
    PATRON_CONTENIDO_GEN = r"(CONTENT|CONTENIDO|INTERIOR|BN)"
    
    patron_apto_pod = re.compile(f"^{re.escape(title_id_limpio)}_CONTENIDO_BN.*_(\\d+)\\.pdf$", re.IGNORECASE)
    patron_master_tipo = re.compile(PATRON_CONTENIDO, re.IGNORECASE)
    patron_tipo_gen = re.compile(PATRON_CONTENIDO_GEN, re.IGNORECASE)
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
            if not archivos_coherencia: return None, "No se encontró un archivo MASTER de interior."
            mejor = max(archivos_coherencia, key=lambda x: x['fecha'])
            return mejor['ruta'], None
        else:
            if not archivos_aptos: return None, "No se encontró un archivo validado (*_CONTENIDO_BN_..._X.pdf)."
            mejor = max(archivos_aptos, key=lambda x: (x['fecha'], x['version']))
            if archivos_totales:
                posterior = max(archivos_totales, key=lambda x: x['fecha'])
                if posterior['fecha'] > mejor['fecha']:
                    msg = f"Se encontró un archivo posterior al validado: `{posterior['nombre']}`. Por favor, corregir el error en el NAS para procesar el validado que tenga la fecha más reciente."
                    return None, msg
            return mejor['ruta'], None
    except: return None, "Error al listar el directorio en el NAS."

def crear_pagina_orden_de_trabajo(trabajo_actual):
    """Crea un nuevo documento PDF de una página A4 con la orden de trabajo."""
    print("      - Creando hoja de orden de trabajo...")
    try:
        A4 = fitz.paper_size("a4")
        margen = 36
        line_height = 12

        use_builtin_fonts = False
        font_reg_id = None
        font_bold_id = None

        doc_ot = fitz.open()
        page = doc_ot.new_page(width=A4[0], height=A4[1])
        
        try:
            if os.path.exists(FONT_REGULAR_PATH) and os.path.exists(FONT_BOLD_PATH):
                font_reg_id = page.insert_font(fontfile=FONT_REGULAR_PATH, fontname="F-Reg")
                font_bold_id = page.insert_font(fontfile=FONT_BOLD_PATH, fontname="F-Bold")
            else:
                raise FileNotFoundError("Custom font files not found.")
        except Exception as e:
            print(f"      WARNING: Fallback to built-in fonts. Error loading custom fonts: {e}")
            use_builtin_fonts = True

        rect_img = fitz.Rect(margen, margen, A4[0] - margen, A4[1] / 2)
        ruta_tapa = trabajo_actual.get('ruta_archivo_tapa')
        if ruta_tapa and os.path.exists(ruta_tapa):
            try:
                import base64
                with fitz.open(ruta_tapa) as doc_tapa:
                    if doc_tapa.page_count > 0:
                        pix_tapa = doc_tapa[0].get_pixmap()
                        page.insert_image(rect_img, pixmap=pix_tapa, keep_proportion=True)
                        
                        img_data = pix_tapa.tobytes("png")
                        trabajo_actual['b64_tapa'] = base64.b64encode(img_data).decode('utf-8')
            except Exception as e:
                print(f"      ADVERTENCIA: No se pudo insertar la imagen de la tapa. Error: {e}")

        barcode_text = trabajo_actual.get('odoo_sale_order_name') or trabajo_actual.get('order_code')
        if barcode_text:
            try:
                import io
                from barcode import Code128
                from barcode.writer import ImageWriter
                buffer = io.BytesIO()
                Code128(barcode_text, writer=ImageWriter()).write(buffer, options={'write_text': False})
                barcode_rect = fitz.Rect((A4[0]-150)/2, margen+5, (A4[0]+150)/2, margen+30)
                page.insert_image(barcode_rect, stream=buffer.getvalue(), keep_proportion=True)
            except Exception as e:
                print(f"      ADVERTENCIA: No se pudo insertar el código de barras. Error: {e}")

        y = A4[1] / 2 + 20

        rect_col_izq = fitz.Rect(margen, y, A4[0] / 2 - 10, A4[1] - margen)
        rect_col_der = fitz.Rect(A4[0] / 2 + 10, y, A4[0] - margen, A4[1] - margen)
        y_izq, y_der = y, y

        def escribir_linea_izq(texto, es_titulo=False, indent=0):
            nonlocal y_izq
            rect = fitz.Rect(rect_col_izq.x0 + indent, y_izq, rect_col_izq.x1, y_izq + line_height)
            if use_builtin_fonts:
                fontname = "helv-bold" if es_titulo else "helv"
                page.insert_textbox(rect, texto, fontsize=10 if es_titulo else 8, fontname=fontname)
            else:
                fontname = "F-Bold" if es_titulo else "F-Reg"
                page.insert_textbox(rect, texto, fontsize=10 if es_titulo else 8, fontname=fontname)
            y_izq += line_height if not es_titulo else (line_height * 1.5)

        def escribir_linea_der(texto, es_titulo=False, indent=0):
            nonlocal y_der
            rect = fitz.Rect(rect_col_der.x0 + indent, y_der, rect_col_der.x1, y_der + line_height)
            if use_builtin_fonts:
                fontname = "helv-bold" if es_titulo else "helv"
                page.insert_textbox(rect, texto, fontsize=10 if es_titulo else 8, fontname=fontname)
            else:
                fontname = "F-Bold" if es_titulo else "F-Reg"
                page.insert_textbox(rect, texto, fontsize=10 if es_titulo else 8, fontname=fontname)
            y_der += line_height if not es_titulo else (line_height * 1.5)

        oc_limpio = limpiar_id(trabajo_actual.get('order_code', ''), 'PED')
        escribir_linea_izq("Libro", es_titulo=True)
        escribir_linea_izq(f"{trabajo_actual.get('title', 'N/A')} ({oc_limpio}-{trabajo_actual.get('line_number', '')})")
        escribir_linea_izq(f"Cantidad: {trabajo_actual.get('quantity_requested', 'N/A')}")
        escribir_linea_izq(f"Tamaño: {trabajo_actual.get('width', '0')} x {trabajo_actual.get('height', '0')} mm")
        escribir_linea_izq(f"Unidad de negocio: {trabajo_actual.get('business_unit', 'N/A')}")
        escribir_linea_izq(f"Tipo: {trabajo_actual.get('order_type', 'N/A')}")
        y_izq += line_height

        escribir_linea_izq("Interior", es_titulo=True)
        escribir_linea_izq(f"Páginas: {trabajo_actual.get('total_pages', 'N/A')}")
        papel_interior_code = trabajo_actual.get('bw_paper_type')
        texto_papel_interior = getattr(mapeos, 'MAPEO_NOMBRES_PAPEL', {}).get(papel_interior_code, papel_interior_code or 'N/A')
        escribir_linea_izq(f"Papel: {texto_papel_interior}")
        tintas_interior = "1/1 negro"
        if int(trabajo_actual.get('color_pages', 0)) > 0: tintas_interior = "4/4 color"
        escribir_linea_izq(f"Tintas: {tintas_interior}")
        escribir_linea_izq(f"Comentarios del cliente: {trabajo_actual.get('publisher_observations', '')}")
        y_izq += line_height
        
        if trabajo_actual.get('color_insert') == 'YES':
            escribir_linea_izq("Insertos color", es_titulo=True)
            escribir_linea_izq(f"Páginas: {trabajo_actual.get('color_pages', 'N/A')}")
            papel_color_code = trabajo_actual.get('color_paper_type')
            texto_papel_color = getattr(mapeos, 'MAPEO_NOMBRES_PAPEL', {}).get(papel_color_code, papel_color_code or 'N/A')
            escribir_linea_izq(f"Papel: {texto_papel_color}")
            y_izq += line_height
            
        escribir_linea_der("Tapas", es_titulo=True)
        escribir_linea_der(f"Lomo: {trabajo_actual.get('spine', '0')} mm")
        escribir_linea_der(f"Tintas: {'4/0' if trabajo_actual.get('cover_printing_type') == 'CO40' else 'N/A'}")
        papel_tapa_code = trabajo_actual.get('cover_paper_type')
        texto_papel_tapa = getattr(mapeos, 'MAPEO_NOMBRES_PAPEL', {}).get(papel_tapa_code, papel_tapa_code or 'N/A')
        escribir_linea_der(f"Papel: {texto_papel_tapa}")
        flaps_width = trabajo_actual.get('flaps_width', '0')
        escribir_linea_der(f"Solapas: {'NO' if str(flaps_width) == '0' else f'{flaps_width} mm'}")
        y_der += line_height

        escribir_linea_der("Terminaciones", es_titulo=True)
        escribir_linea_der(f"Encuadernado: {trabajo_actual.get('binding', 'N/A')}")
        escribir_linea_der(f"Laminado: {trabajo_actual.get('laminate', 'N/A')}")
        escribir_linea_der(f"Filial: {trabajo_actual.get('publisher_facility', 'N/A')}")
        y_der += line_height * 2

        datos_envio = json.loads(trabajo_actual.get('datos_envio_json') or '[]')
        for i, envio in enumerate(datos_envio, 1):
            escribir_linea_der(f"Envío {i}", es_titulo=True)
            for clave, valor in envio.items():
                if not valor or not str(valor).strip(): continue
                if clave == "Titulos":
                    if valor:
                        escribir_linea_der("#### Títulos a enviar")
                        for titulo_envio in valor:
                            escribir_linea_der(f"- {titulo_envio.get('Title', 'N/A')} ({titulo_envio.get('Copies', 0)} copias)", indent=10)
                else:
                    escribir_linea_der(f"{clave}: {valor}")
            y_der += line_height

        return doc_ot
        
    except Exception as e:
        print(f"      ERROR: No se pudo generar la orden de trabajo: {e}")
        return None

def dibujar_lineas_de_corte(page, trim_box, posicion):
    offset = 14.17
    longitud_marca = 14.17
    color_corte = (0, 0, 0, 1)
    x0, y0, x1, y1 = trim_box

    if posicion != 'inferior':
        page.draw_line(fitz.Point(x0, y0 - offset), fitz.Point(x0, y0 - offset - longitud_marca), color=color_corte, width=0.25)
    if posicion != 'derecha':
        page.draw_line(fitz.Point(x0 - offset, y0), fitz.Point(x0 - offset - longitud_marca, y0), color=color_corte, width=0.25)

    if posicion != 'inferior':
        page.draw_line(fitz.Point(x1, y0 - offset), fitz.Point(x1, y0 - offset - longitud_marca), color=color_corte, width=0.25)
    if posicion != 'izquierda':
        page.draw_line(fitz.Point(x1 + offset, y0), fitz.Point(x1 + offset + longitud_marca, y0), color=color_corte, width=0.25)

    if posicion != 'superior':
        page.draw_line(fitz.Point(x0, y1 + offset), fitz.Point(x0, y1 + offset + longitud_marca), color=color_corte, width=0.25)
    if posicion != 'derecha':
        page.draw_line(fitz.Point(x0 - offset, y1), fitz.Point(x0 - offset - longitud_marca, y1), color=color_corte, width=0.25)

    if posicion != 'superior':
        page.draw_line(fitz.Point(x1, y1 + offset), fitz.Point(x1, y1 + offset + longitud_marca), color=color_corte, width=0.25)
    if posicion != 'izquierda':
        page.draw_line(fitz.Point(x1 + offset, y1), fitz.Point(x1 + offset + longitud_marca, y1), color=color_corte, width=0.25)

def procesar_interior(trabajo_actual):
    oc = trabajo_actual.get('order_code')
    ln = trabajo_actual.get('line_number')
    tid = trabajo_actual.get('title_id')
    print(f"    Procesando INTERIOR -> Pedido: {oc} | Línea: {ln} | TitleID: {tid}")
    
    doc_orden_trabajo = crear_pagina_orden_de_trabajo(trabajo_actual)
    if not doc_orden_trabajo:
        print("    ERROR: Se canceló el procesamiento del interior porque no se pudo generar la orden de trabajo.")
        return None

    ruta_orig = trabajo_actual['ruta_archivo_contenido']
    doc = None
    try:
        doc = fitz.open(ruta_orig)
        if doc.page_count == 0:
            doc.close()
            return None
        
        cantidad = int(trabajo_actual['quantity_requested'])
        cajas_normalizadas = obtener_cajas_normalizadas_pypdf(ruta_orig)
        if not cajas_normalizadas:
            doc.close()
            return None

        width_mm_meta = float(trabajo_actual.get('width', 0))
        height_mm_meta = float(trabajo_actual.get('height', 0))
        w_pts_meta = width_mm_meta / MM_PER_POINT
        h_pts_meta = height_mm_meta / MM_PER_POINT

        caja_de_recorte_pdf_original = None
        
        # 1. Intentar validar MediaBox contra metadatos
        caja_media = cajas_normalizadas.get('media')
        if caja_media:
            if abs(caja_media.width - w_pts_meta) < 5 and abs(caja_media.height - h_pts_meta) < 5:
                caja_de_recorte_pdf_original = caja_media
        
        # 2. Si MediaBox no coincide, intentar TrimBox
        if not caja_de_recorte_pdf_original:
            caja_trim = cajas_normalizadas.get('trim')
            if caja_trim:
                if abs(caja_trim.width - w_pts_meta) < 5 and abs(caja_trim.height - h_pts_meta) < 5:
                    caja_de_recorte_pdf_original = caja_trim

        # 3. Fallback: Si ninguno coincide perfectamente, usamos el TrimBox (o MediaBox) y RE-CENTRAMOS
        if not caja_de_recorte_pdf_original:
            caja_temp = cajas_normalizadas.get('trim') or cajas_normalizadas.get('media')
            # Calculamos un nuevo Rect centrado en la caja encontrada usando las medidas de la API
            nx0 = caja_temp.x0 + (caja_temp.width - w_pts_meta) / 2
            ny0 = caja_temp.y0 + (caja_temp.height - h_pts_meta) / 2
            caja_de_recorte_pdf_original = fitz.Rect(nx0, ny0, nx0 + w_pts_meta, ny0 + h_pts_meta)

        try:
            has_bleed = float(trabajo_actual.get('bleed', 0)) > 0
        except (ValueError, TypeError):
            has_bleed = False

        if has_bleed:
            caja_de_calculo_final = fitz.Rect(caja_de_recorte_pdf_original.x0 - BLEED_PTS, caja_de_recorte_pdf_original.y0 - BLEED_PTS,
                                                 caja_de_recorte_pdf_original.x1 + BLEED_PTS, caja_de_recorte_pdf_original.y1 + BLEED_PTS)
        else:
            caja_de_calculo_final = caja_de_recorte_pdf_original

        width_mm = round(caja_de_recorte_pdf_original.width * MM_PER_POINT, 2)
        height_mm = round(caja_de_recorte_pdf_original.height * MM_PER_POINT, 2)
        orientacion = 'V' if height_mm >= width_mm else 'A'

        layout, papel_folder = ("1up", "23x32")
        if orientacion == 'V':
            if (width_mm <= 156 and height_mm <= 221): layout, papel_folder = ("2up", "23x32")
            elif (width_mm <= 171 and height_mm <= 241): layout, papel_folder = ("2up", "25x35")
        elif orientacion == 'A':
            if (width_mm <= 221 and (height_mm * 2) <= 312):
                layout, papel_folder = ("2up", "23x32")

        oc_limpio = limpiar_id(trabajo_actual['order_code'], 'PED')
        papel_resumido = mapeos.MAPEO_PAPEL.get(trabajo_actual['bw_paper_type'], "N_A")
        copias = math.ceil(cantidad / 2) if layout == "2up" and (cantidad % 2 == 0 or cantidad >= 10) else cantidad
        nuevo_nombre = f"{oc_limpio}-{trabajo_actual['line_number']}_{papel_resumido}x{copias}_{orientacion}.pdf"

        imposed_doc = fitz.open()
        papel_dims_cm = [int(d) for d in papel_folder.split('x')]
        
        if layout == "1up":
            papel_w_pts, papel_h_pts = (papel_dims_cm[0] * 10) / MM_PER_POINT, (papel_dims_cm[1] * 10) / MM_PER_POINT
            content_width_on_sheet = caja_de_recorte_pdf_original.width
            content_height_on_sheet = caja_de_recorte_pdf_original.height

            if has_bleed:
                content_width_on_sheet += (2 * BLEED_PTS)
                content_height_on_sheet += (2 * BLEED_PTS)

            for i in range(len(doc)):
                new_page = imposed_doc.new_page(width=papel_w_pts, height=papel_h_pts)
                x_offset = (papel_w_pts - content_width_on_sheet) / 2
                y_offset = (papel_h_pts - content_height_on_sheet) / 2
                target_rect_artwork = fitz.Rect(x_offset, y_offset, x_offset + content_width_on_sheet, y_offset + content_height_on_sheet)
                
                new_page.show_pdf_page(target_rect_artwork, doc, i, clip=caja_de_calculo_final)
                
                trimbox_for_marks = fitz.Rect(target_rect_artwork)
                if has_bleed:
                    trimbox_for_marks.x0 += BLEED_PTS
                    trimbox_for_marks.y0 += BLEED_PTS
                    trimbox_for_marks.x1 -= BLEED_PTS
                    trimbox_for_marks.y1 -= BLEED_PTS
                
                dibujar_lineas_de_corte(new_page, trimbox_for_marks, 'unica')
                
        elif layout == "2up":
            papel_w_pts, papel_h_pts = max((papel_dims_cm[0] * 10) / MM_PER_POINT, (papel_dims_cm[1] * 10) / MM_PER_POINT), \
                                       min((papel_dims_cm[0] * 10) / MM_PER_POINT, (papel_dims_cm[1] * 10) / MM_PER_POINT)

            W_trim = caja_de_recorte_pdf_original.width
            H_trim = caja_de_recorte_pdf_original.height

            imposed_block_width = (2 * W_trim) + (2 * BLEED_PTS if has_bleed else 0)
            imposed_block_height = H_trim + (2 * BLEED_PTS if has_bleed else 0)
            
            margen_vertical = (papel_h_pts - imposed_block_height) / 2
            margen_lateral = (papel_w_pts - imposed_block_width) / 2

            trim_rect_izq_on_sheet = fitz.Rect(
                margen_lateral + (BLEED_PTS if has_bleed else 0),
                margen_vertical + (BLEED_PTS if has_bleed else 0),
                margen_lateral + (BLEED_PTS if has_bleed else 0) + W_trim,
                margen_vertical + (BLEED_PTS if has_bleed else 0) + H_trim
            )
            trim_rect_der_on_sheet = fitz.Rect(
                trim_rect_izq_on_sheet.x1,
                trim_rect_izq_on_sheet.y0,
                trim_rect_izq_on_sheet.x1 + W_trim,
                trim_rect_izq_on_sheet.y1
            )

            target_rect_izq = fitz.Rect(
                trim_rect_izq_on_sheet.x0 - (BLEED_PTS if has_bleed else 0),
                trim_rect_izq_on_sheet.y0 - (BLEED_PTS if has_bleed else 0),
                trim_rect_izq_on_sheet.x1,
                trim_rect_izq_on_sheet.y1 + (BLEED_PTS if has_bleed else 0)
            )
            target_rect_der = fitz.Rect(
                trim_rect_der_on_sheet.x0,
                trim_rect_der_on_sheet.y0 - (BLEED_PTS if has_bleed else 0),
                trim_rect_der_on_sheet.x1 + (BLEED_PTS if has_bleed else 0),
                trim_rect_der_on_sheet.y1 + (BLEED_PTS if has_bleed else 0)
            )

            def get_clip_for_page(page_index):
                clip = fitz.Rect(caja_de_recorte_pdf_original)
                if not has_bleed:
                    return clip
                
                if (page_index + 1) % 2 != 0: 
                    clip.x1 += BLEED_PTS
                else:
                    clip.x0 -= BLEED_PTS
                
                clip.y0 -= BLEED_PTS
                clip.y1 += BLEED_PTS
                return clip

            if cantidad <= 9 and cantidad % 2 != 0:
                total_pages_inicial = len(doc)
                paginas_a_anadir = (4 - total_pages_inicial % 4) % 4
                if paginas_a_anadir > 0:
                    for _ in range(paginas_a_anadir):
                        doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
                
                total_pages = len(doc)
                h = total_pages // 2
                for i in range(h):
                    new_page = imposed_doc.new_page(width=papel_w_pts, height=papel_h_pts)
                    p1_idx, p2_idx = i, i + h

                    clip1 = get_clip_for_page(p1_idx)
                    clip2 = get_clip_for_page(p2_idx)

                    if (i + 1) % 2 != 0:
                        new_page.show_pdf_page(target_rect_izq, doc, p1_idx, rotate=180, clip=clip1)
                        new_page.show_pdf_page(target_rect_der, doc, p2_idx, rotate=0, clip=clip2)
                    else:
                        new_page.show_pdf_page(target_rect_izq, doc, p2_idx, rotate=0, clip=clip2)
                        new_page.show_pdf_page(target_rect_der, doc, p1_idx, rotate=180, clip=clip1)
                    
                    dibujar_lineas_de_corte(new_page, trim_rect_izq_on_sheet, 'izquierda')
                    dibujar_lineas_de_corte(new_page, trim_rect_der_on_sheet, 'derecha')

            else:
                total_pages = len(doc)
                for i in range(total_pages):
                    new_page = imposed_doc.new_page(width=papel_w_pts, height=papel_h_pts)
                    clip = get_clip_for_page(i)

                    if (i + 1) % 2 != 0:
                        new_page.show_pdf_page(target_rect_izq, doc, i, rotate=180, clip=clip)
                        new_page.show_pdf_page(target_rect_der, doc, i, rotate=0, clip=clip)
                    else:
                        new_page.show_pdf_page(target_rect_izq, doc, i, rotate=0, clip=clip)
                        new_page.show_pdf_page(target_rect_der, doc, i, rotate=180, clip=clip)

                    dibujar_lineas_de_corte(new_page, trim_rect_izq_on_sheet, 'izquierda')
                    dibujar_lineas_de_corte(new_page, trim_rect_der_on_sheet, 'derecha')
        
        doc.close()

        imposed_doc.insert_pdf(doc_orden_trabajo, start_at=0)

        rutas_guardadas = []
        rutas_destino_base = []
        if cantidad < 10:
            rutas_destino_base.append(os.path.join(mapeos.DEST_PATH_INTERIOR, "Ricoh 8310", papel_folder))
        else:
            rutas_destino_base.append(os.path.join(mapeos.DEST_PATH_INTERIOR, "Ricoh 8310", papel_folder))
            rutas_destino_base.append(os.path.join(mapeos.DEST_PATH_INTERIOR, "Ricoh 8420", papel_folder))

        for ruta in rutas_destino_base:
            os.makedirs(ruta, exist_ok=True)
            ruta_final = os.path.join(ruta, nuevo_nombre)
            imposed_doc.save(ruta_final)
            rutas_guardadas.append(ruta_final)
        
        imposed_doc.close()

        return rutas_guardadas
    except Exception as e:
        print(f"      ERROR procesando interior: {e}")
        if doc: doc.close()
        return None

def run():
    if not mapeos.PROCESAR_PDF_ACTIVADO: return
    print("--- Script 6 (INTERIOR) ---")

    conn = None
    trabajos = []
    try:
        conn = db_conn.conectar_db()
        if conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' for _ in mapeos.ESTADOS_A_EXCLUIR_PRODUCCION)
            query = f"SELECT * FROM trabajos WHERE odoo_pickings_data_json IS NOT NULL AND estado_tapa_produccion = ? AND (estado_interior_produccion IS NULL OR estado_interior_produccion = ?) AND (line_status_id IS NULL OR line_status_id NOT IN ({placeholders}))"
            
            params = [mapeos.LOCAL_DB_STATUS_TAPA_GENERADO, mapeos.LOCAL_DB_STATUS_INTERIOR_PENDIENTE] + mapeos.ESTADOS_A_EXCLUIR_PRODUCCION
            cursor.execute(query, params)
            
            trabajos = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"ERROR en Script 6 al consultar la base de datos: {e}")
    finally:
        if conn:
            conn.close()
    
    if not trabajos:
        return

    odoo_api = odoo_conn.conectar_odoo() if trabajos else None

    for t in trabajos:
        rt = t.get('ruta_trabajo')
        tid = limpiar_id(t.get('title_id', ''), 'PAP')
        if rt:
            r_orig, error_msg = encontrar_archivo_mas_reciente(rt, tid, 'CONTENIDO', t.get('order_type', ''))
            if r_orig:
                t['ruta_archivo_contenido'] = r_orig
                res = procesar_interior(t)
                if res:
                    conn = db_conn.conectar_db(); cursor = conn.cursor()
                    cursor.execute("UPDATE trabajos SET estado_interior_produccion = 'GENERADO', ruta_archivo_contenido = ? WHERE order_code = ? AND line_number = ?", 
                                   (res[0], t['order_code'], t['line_number']))
                    conn.commit(); conn.close()
                    print(f"  ✅ Interior {t['order_code']} OK")
                    
                    try:
                        if odoo_api and t.get('odoo_sale_order_id'):
                            so = odoo_api.env['sale.order'].browse(t['odoo_sale_order_id'])
                            
                            attachment_ids = []
                            b64_tapa = t.get('b64_tapa')
                            if b64_tapa:
                                try:
                                    att = odoo_api.env['ir.attachment'].create({
                                        'name': "tapa-miniatura.png",
                                        'type': 'binary',
                                        'datas': b64_tapa,
                                        'res_model': 'sale.order',
                                        'res_id': t['odoo_sale_order_id'],
                                        'mimetype': 'image/png'
                                    })
                                    attachment_ids.append(att)
                                except Exception as e_att:
                                    print(f"      ADVERTENCIA: No se pudo subir el adjunto a Odoo: {e_att}")
                                    
                            so.message_post(
                                body=f"✅ **Producción Interior:** Generado correctamente.\nArchivos: `{', '.join([os.path.basename(r) for r in res])}`",
                                attachment_ids=attachment_ids
                            )
                    except: pass
                else:
                    # Marcar como error en la DB para no trabar el loop
                    conn = db_conn.conectar_db(); cursor = conn.cursor()
                    cursor.execute("UPDATE trabajos SET estado_interior_produccion = 'ERROR' WHERE order_code = ? AND line_number = ?", 
                                   (t['order_code'], t['line_number']))
                    conn.commit(); conn.close()
                    print(f"  ❌ Error al procesar Interior {t['order_code']}")
                    try:
                        if odoo_api and t.get('odoo_sale_order_id'):
                            so = odoo_api.env['sale.order'].browse(t['odoo_sale_order_id'])
                            body = f"⚠️ **Producción Interior:** Error al procesar archivo físico (medidas incorrectas o archivo dañado).\nTitleID: {tid}"
                            so.message_post(body=body)
                    except: pass
            else:
                try:
                    if odoo_api and t.get('odoo_sale_order_id'):
                        so = odoo_api.env['sale.order'].browse(t['odoo_sale_order_id'])
                        body = f"⚠️ **Producción Interior:** {error_msg}\nTitleID: {tid}"
                        so.message_post(body=body)
                except: pass

if __name__ == "__main__":
    run()