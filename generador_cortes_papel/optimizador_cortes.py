# -*- coding: utf-8 -*- 

import math
import multiprocessing
import numpy as np
from collections import defaultdict
from itertools import groupby
import argparse
import sqlite3
import os
import datetime
from tqdm import tqdm

try:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
except ImportError:
    print("Error: La librería 'matplotlib' no está instalada. Por favor, instálala con 'pip install matplotlib' y vuelve a intentarlo.")
    exit(1)

"""
Script para encontrar tamaños de corte óptimos, usando un algoritmo personalizado,
guardando los resultados en una base de datos SQLite y generando PDFs con los layouts.
Implementa un sistema de caché para no recalcular análisis ya realizados.
"""

# --- Lógica de Cálculo (Traducción de JavaScript) ---

def acomoda(d1, d2, corte_ancho, corte_largo, acomodo_corte):
    b, h = d1, d2
    if acomodo_corte == 'H': cb, ch = max(corte_ancho, corte_largo), min(corte_ancho, corte_largo)
    elif acomodo_corte == 'V': cb, ch = min(corte_ancho, corte_largo), max(corte_ancho, corte_largo)
    else: cb, ch = corte_ancho, corte_largo

    if cb <= 0 or ch <= 0: return {'cortesT': 0, 'cortesB': 0, 'cortesH': 0, 'sobranteB': b, 'sobranteH': h, 'layout': []}

    cortesB = math.floor(b / cb) if cb > 0 else 0
    cortesH = math.floor(h / ch) if ch > 0 else 0
    layout = [{'x': i * cb, 'y': j * ch, 'ancho': cb, 'largo': ch} for i in range(cortesB) for j in range(cortesH)]
    return {'cortesT': cortesB * cortesH, 'cortesB': cortesB, 'cortesH': cortesH, 'sobranteB': b - (cortesB * cb), 'sobranteH': h - (cortesH * ch), 'layout': layout}

def calcular_cortes_custom(papel_ancho, papel_largo, corte_ancho, corte_largo):
    b, h = max(papel_ancho, papel_largo), min(papel_ancho, papel_largo)
    cb, ch = max(corte_ancho, corte_largo), min(corte_ancho, corte_largo)

    cortes_base_1 = acomoda(b, h, cb, ch, "H")
    total_cortes_1, mejor_layout_1 = cortes_base_1['cortesT'], cortes_base_1['layout']
    for x in range(cortes_base_1['cortesH'] + 1):
        a1h = h - ((ch * x) + cortes_base_1['sobranteH'])
        a2h = h - a1h
        corteA1, corteA2 = acomoda(b, a1h, cb, ch, "H"), acomoda(b, a2h, ch, cb, "V")
        if (corteA1['cortesT'] + corteA2['cortesT']) > total_cortes_1:
            total_cortes_1 = corteA1['cortesT'] + corteA2['cortesT']
            layout_A2 = corteA2['layout']
            for p in layout_A2: p['y'] += a1h
            mejor_layout_1 = corteA1['layout'] + layout_A2

    cortes_base_2 = acomoda(b, h, cb, ch, "H")
    total_cortes_2, mejor_layout_2 = cortes_base_2['cortesT'], cortes_base_2['layout']
    for x in range(cortes_base_2['cortesB'] + 1):
        a1b = b - ((cb * x) + cortes_base_2['sobranteB'])
        a2b = b - a1b
        corteA1, corteA2 = acomoda(a1b, h, cb, ch, "H"), acomoda(a2b, h, ch, cb, "V")
        if (corteA1['cortesT'] + corteA2['cortesT']) > total_cortes_2:
            total_cortes_2 = corteA1['cortesT'] + corteA2['cortesT']
            layout_A2 = corteA2['layout']
            for p in layout_A2: p['x'] += a1b
            mejor_layout_2 = corteA1['layout'] + layout_A2

    return (total_cortes_1, mejor_layout_1) if total_cortes_1 > total_cortes_2 else (total_cortes_2, mejor_layout_2)

# --- Lógica de Generación de PDF (Corregida) ---

def _draw_dimension(ax, p1, p2, text, dim_line_pos, offset, is_vertical=False, color='black', fontsize=8, with_extension_lines=True):
    if is_vertical:
        start_old = (dim_line_pos + offset, p1[1])
        end_old = (dim_line_pos + offset, p2[1])
    else:
        start_old = (p1[0], dim_line_pos + offset)
        end_old = (p2[0], dim_line_pos + offset)
    print(f"DEBUG COTA: start={start_old}, end={end_old}, text='{text}', offset={offset}, is_vertical={is_vertical}, color={color}")

    line_style, arrow_style, linewidth, text_offset = '-', '-|>', 0.7, 0.5
    ext_line_style = ':'
    ext_linewidth = 0.5

    if is_vertical:
        dim_line_x = dim_line_pos + offset
        mid_point_y = p1[1] + (p2[1] - p1[1]) / 2

        ax.plot([dim_line_x, dim_line_x], [p1[1], p2[1]], color=color, lw=linewidth, ls=line_style)
        ax.annotate("", xy=(dim_line_x, p1[1]), xytext=(dim_line_x, mid_point_y), arrowprops=dict(arrowstyle=arrow_style, color=color, lw=linewidth, shrinkA=0, shrinkB=0))
        ax.annotate("", xy=(dim_line_x, p2[1]), xytext=(dim_line_x, mid_point_y), arrowprops=dict(arrowstyle=arrow_style, color=color, lw=linewidth, shrinkA=0, shrinkB=0))
        ax.text(dim_line_x + text_offset, mid_point_y, text, va='center', ha='left', rotation='vertical', fontsize=fontsize, color=color)

        if with_extension_lines:
            ax.plot([p1[0], dim_line_x], [p1[1], p1[1]], color=color, lw=ext_linewidth, ls=ext_line_style)
            ax.plot([p2[0], dim_line_x], [p2[1], p2[1]], color=color, lw=ext_linewidth, ls=ext_line_style)
    else: # Horizontal
        dim_line_y = dim_line_pos + offset
        mid_point_x = p1[0] + (p2[0] - p1[0]) / 2

        ax.plot([p1[0], p2[0]], [dim_line_y, dim_line_y], color=color, lw=linewidth, ls=line_style)
        ax.annotate("", xy=(p1[0], dim_line_y), xytext=(mid_point_x, dim_line_y), arrowprops=dict(arrowstyle=arrow_style, color=color, lw=linewidth, shrinkA=0, shrinkB=0))
        ax.annotate("", xy=(p2[0], dim_line_y), xytext=(mid_point_x, dim_line_y), arrowprops=dict(arrowstyle=arrow_style, color=color, lw=linewidth, shrinkA=0, shrinkB=0))
        ax.text(mid_point_x, dim_line_y + text_offset, text, va='bottom', ha='center', fontsize=fontsize, color=color)

        if with_extension_lines:
            ax.plot([p1[0], p1[0]], [p1[1], dim_line_y], color=color, lw=ext_linewidth, ls=ext_line_style)
            ax.plot([p2[0], p2[0]], [p2[1], dim_line_y], color=color, lw=ext_linewidth, ls=ext_line_style)

def generar_pdf_layout(pliego_cm, corte_cm, piezas, layout, filename):
    print(f"\n--- DEBUG: Iniciando generacion de {filename} ---")
    print(f"--- DEBUG: Layout Recibido ---")
    for p in layout:
        print(p)
    print("--- FIN DEBUG ---")

    pliego_w, pliego_h = max(pliego_cm), min(pliego_cm)
    corte_w, corte_h = corte_cm
    fig, ax = plt.subplots(figsize=(12, 12 * pliego_h / pliego_w if pliego_w > 0 else 12))

    ax.set_aspect('equal'); ax.axis('off')

    if layout:
        # Mover el layout a la derecha para que el sobrante principal quede a la izquierda.
        max_x_unmodified = max(p['x'] + p['ancho'] for p in layout)
        sobrante_x_total = pliego_w - max_x_unmodified
        offset_x = sobrante_x_total
        for p in layout:
            p['x'] += offset_x

    ax.add_patch(Rectangle((0, 0), pliego_w, pliego_h, fc='#EAEAEA', ec='black', lw=1))
    for p in layout: ax.add_patch(Rectangle((p['x'], p['y']), p['ancho'], p['largo'], fc='#4682B4', ec='white', lw=0.8))
    
    margin = max(pliego_w, pliego_h) * 0.05
    offset_pieces = margin * 0.8
    offset_leftovers = margin * 1.6
    offset_sheet = margin * 2.4

    # Capa 3: Dimensiones generales del pliego
    _draw_dimension(ax, (0, 0), (pliego_w, 0), f'{pliego_w:.1f} cm', 0, -offset_sheet, with_extension_lines=False, color='black')
    _draw_dimension(ax, (0, 0), (0, pliego_h), f'{pliego_h:.1f} cm', 0, -offset_sheet, is_vertical=True, with_extension_lines=False, color='black')

    if layout:
        min_x_layout = min(p['x'] for p in layout)
        max_x_layout = max(p['x'] + p['ancho'] for p in layout)
        min_y_layout = min(p['y'] for p in layout)
        max_y_layout = max(p['y'] + p['largo'] for p in layout)

        # Capa 1: Dimensiones de piezas
        for p in layout:
            if abs(p['y'] - min_y_layout) < 0.1:
                _draw_dimension(ax, (p['x'], p['y']), (p['x'] + p['ancho'], p['y']), f"{p['ancho']:.1f}", 0, -offset_pieces, is_vertical=False, color='#4682B4', fontsize=7)
            is_top_exposed = not any(abs(o['y'] - (p['y'] + p['largo'])) < 0.1 and max(p['x'], o['x']) < min(p['x'] + p['ancho'], o['x'] + o['ancho']) for o in layout if o is not p)
            if is_top_exposed:
                _draw_dimension(ax, (p['x'], p['y'] + p['largo']), (p['x'] + p['ancho'], p['y'] + p['largo']), f"{p['ancho']:.1f}", pliego_h, offset_pieces, is_vertical=False, color='#4682B4', fontsize=7)
            if abs(p['x'] - min_x_layout) < 0.1:
                _draw_dimension(ax, (p['x'], p['y']), (p['x'], p['y'] + p['largo']), f"{p['largo']:.1f}", 0, -offset_pieces, is_vertical=True, color='#4682B4', fontsize=7)
            is_right_exposed = not any(abs(o['x'] - (p['x'] + p['ancho'])) < 0.1 and max(p['y'], o['y']) < min(p['y'] + p['largo'], o['y'] + o['largo']) for o in layout if o is not p)
            if is_right_exposed:
                _draw_dimension(ax, (p['x'] + p['ancho'], p['y']), (p['x'] + p['ancho'], p['y'] + p['largo']), f"{p['largo']:.1f}", pliego_w, offset_pieces, is_vertical=True, color='#4682B4', fontsize=7)

        # Capa 2: Dimensiones de sobrantes
        sobrante_izquierda = min_x_layout
        sobrante_derecha = pliego_w - max_x_layout
        sobrante_abajo = min_y_layout
        
        if sobrante_izquierda > 0.1:
            _draw_dimension(ax, (0, 0), (min_x_layout, 0), f'{sobrante_izquierda:.1f} cm', 0, -offset_leftovers, color='grey', fontsize=7)
        if sobrante_derecha > 0.1:
            _draw_dimension(ax, (max_x_layout, 0), (pliego_w, 0), f'{sobrante_derecha:.1f} cm', 0, -offset_leftovers, color='grey', fontsize=7)
        if sobrante_abajo > 0.1:
            _draw_dimension(ax, (0, 0), (0, min_y_layout), f'{sobrante_abajo:.1f} cm', 0, -offset_leftovers, is_vertical=True, color='grey', fontsize=7)

        x_coords = set([min_x_layout, max_x_layout])
        for p in layout:
            x_coords.add(p['x'])
            x_coords.add(p['x'] + p['ancho'])
        sorted_x = sorted(list(x_coords))

        if len(sorted_x) > 1:
            strips = []
            for i in range(len(sorted_x) - 1):
                x1, x2 = sorted_x[i], sorted_x[i+1]
                if x2 - x1 < 0.1: continue
                
                max_y_in_strip = 0
                for p in layout:
                    if max(p['x'], x1) < min(p['x'] + p['ancho'], x2):
                        max_y_in_strip = max(max_y_in_strip, p['y'] + p['largo'])
                strips.append({'x1': x1, 'x2': x2, 'max_y': max_y_in_strip})

            merged_strips = []
            if strips:
                current_strip = strips[0]
                for next_strip in strips[1:]:
                    if abs(next_strip['max_y'] - current_strip['max_y']) < 0.1 and abs(next_strip['x1'] - current_strip['x2']) < 0.1:
                        current_strip['x2'] = next_strip['x2']
                    else:
                        merged_strips.append(current_strip)
                        current_strip = next_strip
                merged_strips.append(current_strip)

            for i, s in enumerate(merged_strips):
                sobrante_h = pliego_h - s['max_y']
                if sobrante_h > 0.1:
                    _draw_dimension(ax, (s['x1'], pliego_h), (s['x2'], pliego_h), f"{(s['x2'] - s['x1']):.1f}", pliego_h, offset_leftovers, color='grey', fontsize=7)
                    
                    if abs(s['x1'] - min_x_layout) < 0.1:
                        _draw_dimension(ax, (s['x1'], s['max_y']), (s['x1'], pliego_h), f'{sobrante_h:.1f} cm', 0, -offset_leftovers, is_vertical=True, color='grey', fontsize=7)
                    if abs(s['x2'] - max_x_layout) < 0.1 and abs(s['x1'] - min_x_layout) > 0.1:
                        _draw_dimension(ax, (s['x2'], s['max_y']), (s['x2'], pliego_h), f'{sobrante_h:.1f} cm', pliego_w, offset_leftovers, is_vertical=True, color='grey', fontsize=7)

    ax.set_xlim(-offset_sheet * 1.2, pliego_w + offset_sheet * 1.2)
    ax.set_ylim(-offset_sheet * 1.2, pliego_h + offset_sheet * 1.2)
    area_utilizada = (piezas * corte_w * corte_h) / (pliego_w * pliego_h) * 100 if pliego_w > 0 and pliego_h > 0 else 0
    title = f"Pliego: {pliego_w:.1f}x{pliego_h:.1f} cm | Corte: {corte_w:.1f}x{corte_h:.1f} cm | Piezas: {piezas} | Uso: {area_utilizada:.1f}%"
    ax.set_title(title, fontsize=12)
    
    plt.savefig(filename, bbox_inches='tight', pad_inches=0.3); plt.close(fig)
    print(f"Generado PDF: {filename}")

# --- Lógica de Base de Datos y Caché ---

def inicializar_db(db_path):
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS analisis (id INTEGER PRIMARY KEY, ts TEXT, p_w REAL, p_h REAL, min_w REAL, min_h REAL, max_w REAL, max_h REAL, inc REAL, UNIQUE(p_w,p_h,min_w,min_h,max_w,max_h,inc))")
        c.execute("CREATE TABLE IF NOT EXISTS resultados (id INTEGER PRIMARY KEY, analisis_id INTEGER, ancho REAL, alto REAL, piezas INTEGER, FOREIGN KEY(analisis_id) REFERENCES analisis(id))")
        c.execute("CREATE TABLE IF NOT EXISTS layouts (id INTEGER PRIMARY KEY, resultado_id INTEGER, x REAL, y REAL, ancho REAL, largo REAL, FOREIGN KEY(resultado_id) REFERENCES resultados(id))")

def check_cache(db, p, mi, ma, inc):
    # Normaliza todas las dimensiones antes de buscar para consistencia.
    p_w, p_h = max(p), min(p)
    mi_w, mi_h = max(mi), min(mi)
    ma_w, ma_h = max(ma), min(ma)
    with sqlite3.connect(db) as conn:
        # La búsqueda ahora es simple porque los datos siempre se guardan normalizados.
        return conn.cursor().execute(
            "SELECT id FROM analisis WHERE p_w=? AND p_h=? AND min_w=? AND min_h=? AND max_w=? AND max_h=? AND inc=?",
            (p_w, p_h, mi_w, mi_h, ma_w, ma_h, inc)
        ).fetchone()

def fetch_cached_results(db, analisis_id):
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        res = conn.cursor().execute("SELECT * FROM resultados WHERE analisis_id=?", (analisis_id,)).fetchall()
        return [dict(r) for r in res]

def guardar_analisis_completo(db, p, mi, ma, inc, cortes_optimos):
    # Normaliza todas las dimensiones antes de guardar para consistencia.
    p_w, p_h = max(p), min(p)
    mi_w, mi_h = max(mi), min(mi)
    ma_w, ma_h = max(ma), min(ma)

    with sqlite3.connect(db) as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO analisis (ts, p_w, p_h, min_w, min_h, max_w, max_h, inc) VALUES (?,?,?,?,?,?,?,?)", (datetime.datetime.now().isoformat(), p_w, p_h, mi_w, mi_h, ma_w, ma_h, inc))
            analisis_id = c.lastrowid
            print(f"Nuevo análisis con ID {analisis_id} guardado en la base de datos.")
            for corte in cortes_optimos:
                c.execute("INSERT INTO resultados (analisis_id, ancho, alto, piezas) VALUES (?,?,?,?)", (analisis_id, corte['ancho'], corte['alto'], corte['piezas']))
                resultado_id = c.lastrowid
                _, layout = calcular_cortes_custom(p[0], p[1], corte['ancho'], corte['alto'])
                if layout:
                    piezas_layout = [(resultado_id, pieza['x'], pieza['y'], pieza['ancho'], pieza['largo']) for pieza in layout]
                    c.executemany('INSERT INTO layouts (resultado_id, x, y, ancho, largo) VALUES (?, ?, ?, ?, ?)', piezas_layout)
            conn.commit()
        except sqlite3.IntegrityError: print("Error al guardar análisis, probablemente ya existe.")

# --- Lógica de Búsqueda y Paralelización ---

def worker(args): return {'ancho': args[2], 'alto': args[3], 'piezas': p} if (p := calcular_cortes_custom(*args)[0]) > 0 else None

def encontrar_cortes_optimos(papel_cm, minimo_cm, maximo_cm, incremento, cortes_forzados_cm=[]):
    print(f"Analizando pliego de {papel_cm[0]}x{papel_cm[1]} cm...")
    # --- CORRECCIÓN FINAL: Los parámetros ya vienen normalizados. Usarlos directamente. ---
    # La lógica anterior era confusa y propensa a errores de índice.
    # Esta nueva lógica es explícita y correcta.
    # Rango para el ancho (w): desde el mínimo de los anchos hasta el máximo.
    # Rango para el alto (h): desde el mínimo de los altos hasta el máximo.
    ancho_min, ancho_max = minimo_cm[1], maximo_cm[1]
    alto_min, alto_max = minimo_cm[0], maximo_cm[0]
    tasks = [(papel_cm[0], papel_cm[1], round(w, 2), round(h, 2)) for w in np.arange(ancho_min, ancho_max + incremento, incremento) for h in np.arange(alto_min, alto_max + incremento, incremento)]
    
    # Añadir los cortes forzados a las tareas, asegurando que no estén duplicados
    if cortes_forzados_cm:
        print(f"Añadiendo {len(cortes_forzados_cm)} cortes forzados al análisis.")
        for corte_f in cortes_forzados_cm:
            task_forzada = (papel_cm[0], papel_cm[1], round(corte_f[0], 2), round(corte_f[1], 2))
            if task_forzada not in tasks:
                tasks.append(task_forzada)

    print(f"Se van a procesar {len(tasks)} combinaciones...")
    with multiprocessing.Pool() as pool: resultados = list(tqdm(pool.imap_unordered(worker, tasks), total=len(tasks), desc="Procesando"))
    resultados = [r for r in resultados if r]
    print(f"\nSe generaron {len(resultados)} combinaciones válidas.")
    if not resultados: return []
    grupos = defaultdict(list); [grupos[r['piezas']].append(r) for r in resultados]
    cortes_interesantes = []
    print("Optimizando resultados...")
    for piezas, grupo in sorted(grupos.items(), reverse=True):
        grupo.sort(key=lambda r: r['ancho'] * r['alto'], reverse=True)
        optimos_del_grupo = []
        for actual in grupo:
            es_dominado = False
            actual_dims = sorted((actual['ancho'], actual['alto']))
            for optimo in optimos_del_grupo:
                optimo_dims = sorted((optimo['ancho'], optimo['alto']))
                if all(ad <= od for ad, od in zip(actual_dims, optimo_dims)):
                    es_dominado = True
                    break
            if not es_dominado:
                optimos_del_grupo.append(actual)
        cortes_interesantes.extend(optimos_del_grupo)

    # Asegurarse de que los cortes forzados estén en la lista final
    if cortes_forzados_cm:
        cortes_interesantes_dims = {(round(c['ancho'], 2), round(c['alto'], 2)) for c in cortes_interesantes}
        for resultado in resultados:
            resultado_dims = (round(resultado['ancho'], 2), round(resultado['alto'], 2))
            # Si es un corte forzado y no está ya en la lista de óptimos, lo añadimos
            if any(resultado_dims == (round(cf[0], 2), round(cf[1], 2)) for cf in cortes_forzados_cm):
                if resultado_dims not in cortes_interesantes_dims:
                    cortes_interesantes.append(resultado)
    print(f"Se encontraron {len(cortes_interesantes)} cortes potencialmente óptimos.")
    return cortes_interesantes

# --- Nueva Función para Agregar Cortes Manualmente ---

def agregar_corte_a_analisis_existente(db_path, pliego_cm, corte_cm, no_pdf=False):
    """
    Añade un corte específico a un análisis existente en la base de datos.
    Esta función está integrada en el script principal para evitar duplicación.
    """
    if not os.path.exists(db_path):
        print(f"❌ Error: La base de datos '{db_path}' no existe.")
        return

    pliego_w, pliego_h = pliego_cm
    corte_w, corte_h = corte_cm

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Búsqueda normalizada: busca el análisis sin importar el orden de las dimensiones del pliego.
        cursor.execute("""
            SELECT id FROM analisis
            WHERE (p_w = ? AND p_h = ?) OR (p_w = ? AND p_h = ?)
            ORDER BY ts DESC LIMIT 1
        """, (pliego_w, pliego_h, pliego_h, pliego_w))
        analisis_row = cursor.fetchone()

        if not analisis_row:
            print(f"❌ No se encontró ningún análisis previo para el pliego {pliego_w}x{pliego_h} cm.")
            print("   Por favor, ejecuta primero el optimizador sin '--agregar-corte' para este pliego.")
            return

        analisis_id = analisis_row['id']
        print(f"✅ Análisis encontrado (ID: {analisis_id}) para el pliego {pliego_w}x{pliego_h} cm.")

        cursor.execute("SELECT id FROM resultados WHERE analisis_id = ? AND ancho = ? AND alto = ?", (analisis_id, corte_w, corte_h))
        if (res_existente := cursor.fetchone()):
            print(f"👍 El corte {corte_w}x{corte_h} cm ya existía (Resultado ID: {res_existente['id']}). No se requiere acción.")
            return

        print(f"⏳ El corte {corte_w}x{corte_h} cm no existe. Calculando y agregándolo...")
        piezas, layout = calcular_cortes_custom(pliego_w, pliego_h, corte_w, corte_h)

        if piezas == 0:
            print(f"❌ El corte {corte_w}x{corte_h} cm no entra ni una sola vez en el pliego. No se puede agregar.")
            return

        cursor.execute("INSERT INTO resultados (analisis_id, ancho, alto, piezas) VALUES (?, ?, ?, ?)", (analisis_id, corte_w, corte_h, piezas))
        resultado_id = cursor.lastrowid

        if layout:
            piezas_layout = [(resultado_id, p['x'], p['y'], p['ancho'], p['largo']) for p in layout]
            cursor.executemany('INSERT INTO layouts (resultado_id, x, y, ancho, largo) VALUES (?, ?, ?, ?, ?)', piezas_layout)

        conn.commit()
        print(f"🎉 ¡Agregado! El corte {corte_w}x{corte_h} cm rinde {piezas} piezas (Resultado ID: {resultado_id}).")

        if not no_pdf:
            pdf_dir = "layouts_pdf"; os.makedirs(pdf_dir, exist_ok=True)
            filename = os.path.join(pdf_dir, f"Corte_{int(pliego_w*10)}x{int(pliego_h*10)}_{int(corte_w*10)}x{int(corte_h*10)}.pdf")
            print(f"🎨 Generando PDF del layout en '{filename}'...")
            generar_pdf_layout(pliego_cm, corte_cm, piezas, layout, filename)

# --- Nueva Función para Listar Análisis ---

def listar_analisis_db(db_path):
    """
    Lista todos los análisis guardados en la base de datos.
    """
    print(f"\n--- 🔎 Listando Análisis Guardados en '{db_path}' ---")
    if not os.path.exists(db_path):
        print(f"❌ Error: La base de datos '{db_path}' no existe.")
        return

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM analisis ORDER BY id DESC")
        analisis_todos = cursor.fetchall()

        if not analisis_todos:
            print("No se encontraron análisis en la base de datos.")
            return

        print(f"\nSe encontraron {len(analisis_todos)} análisis:")
        print("-" * 80)
        print(f"{'ID':<5} {'Timestamp':<22} {'Pliego':<15} {'Mínimo':<15} {'Máximo':<15} {'Inc.':<5}")
        print("-" * 80)
        for a in analisis_todos:
            ts = datetime.datetime.fromisoformat(a['ts']).strftime('%Y-%m-%d %H:%M')
            pliego_str = f"{a['p_w']:.1f}x{a['p_h']:.1f}"
            min_str = f"{a['min_w']:.1f}x{a['min_h']:.1f}"
            max_str = f"{a['max_w']:.1f}x{a['max_h']:.1f}"
            print(f"{a['id']:<5} {ts:<22} {pliego_str:<15} {min_str:<15} {max_str:<15} {a['inc']:<5.2f}")
        print("-" * 80)

# --- Ejecución Principal ---

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Encuentra cortes óptimos y los guarda en DB.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--pliego', type=str, default='72x102', help="Tamaño del pliego en cm. Ej: '72x102'")
    parser.add_argument('--minimo', type=str, default='15x20', help="[Optimizador] Tamaño mínimo de corte. Ej: '15x20'")
    parser.add_argument('--maximo', type=str, help="[Optimizador] Tamaño máximo de corte. Por defecto, el tamaño del pliego.")
    parser.add_argument('--incremento', type=float, default=0.1, help="[Optimizador] Incremento para la búsqueda. Ej: 0.5")
    parser.add_argument('--cortes-forzados', type=str, help="[Optimizador] Lista de cortes a incluir en el análisis. Ej: '21x29.7,15x21'")
    parser.add_argument('--agregar-corte', type=str, help="[Modo Manual] Agrega un corte a un análisis existente. Ej: '21x29.7'")
    parser.add_argument('--listar-analisis', action='store_true', help="[Modo Info] Lista todos los análisis guardados en la DB.")
    parser.add_argument('--db', type=str, default='cortes_optimos.db', help="Ruta a la base de datos SQLite.")
    parser.add_argument('--no-pdf', action='store_true', help="Evita la generación de PDFs.")
    args = parser.parse_args()

    inicializar_db(args.db)

    # --- Lógica de Modos de Ejecución ---
    if args.listar_analisis:
        # MODO: Listar análisis existentes
        listar_analisis_db(args.db)
        exit()
    elif args.agregar_corte:
        # MODO: Agregar un corte manualmente a un análisis existente
        print("\n--- MODO: Agregar Corte Manual ---")
        try:
            pliego_cm = tuple(map(float, args.pliego.split('x')))
            corte_a_agregar_cm = tuple(map(float, args.agregar_corte.split('x')))
            agregar_corte_a_analisis_existente(args.db, pliego_cm, corte_a_agregar_cm, args.no_pdf)
        except (ValueError, IndexError):
            print("Error: Formato de tamaño inválido para --pliego o --agregar-corte. Use 'anchoXalto'."); exit(1)
    else:
        # MODO: Optimización completa (comportamiento original)
        print("\n--- MODO: Optimización de Cortes ---")
        try:
            # Normalizamos las dimensiones desde el principio para consistencia
            p_dims = tuple(map(float, args.pliego.split('x')))
            pliego_cm = (max(p_dims), min(p_dims))

            mi_dims = tuple(map(float, args.minimo.split('x')))
            minimo_cm = (max(mi_dims), min(mi_dims))

            ma_dims = tuple(map(float, args.maximo.split('x'))) if args.maximo else pliego_cm
            maximo_cm = (max(ma_dims), min(ma_dims))

        except (ValueError, IndexError):
            print("Error: Formato de tamaño inválido para --pliego, --minimo o --maximo."); exit(1)

        cortes_forzados_cm = []
        if args.cortes_forzados:
            try:
                cortes_forzados_cm = [tuple(map(float, c.split('x'))) for c in args.cortes_forzados.split(',')]
            except (ValueError, IndexError):
                print("Error: Formato de --cortes-forzados inválido. Use 'ancho1xalto1,ancho2xalto2'."); exit(1)

        # --- CORRECCIÓN CLAVE: Siempre intentar usar la caché ---
        cached_id = check_cache(args.db, pliego_cm, minimo_cm, maximo_cm, args.incremento)
        
        if cached_id:
            print(f"Análisis encontrado en caché (ID: {cached_id[0]}). Cargando resultados desde la base de datos...")
            cortes_optimos = fetch_cached_results(args.db, cached_id[0])
            # Si hay cortes forzados, nos aseguramos de que estén presentes.
            if cortes_forzados_cm:
                print("Asegurando la presencia de cortes forzados en los resultados cacheados...")
                cortes_existentes_dims = {(round(c['ancho'], 2), round(c['alto'], 2)) for c in cortes_optimos}
                for corte_f in cortes_forzados_cm:
                    corte_f_dims = (round(corte_f[0], 2), round(corte_f[1], 2))
                    if corte_f_dims not in cortes_existentes_dims:
                        print(f" -> Añadiendo corte forzado faltante: {corte_f_dims[0]}x{corte_f_dims[1]} cm")
                        agregar_corte_a_analisis_existente(args.db, pliego_cm, corte_f, args.no_pdf)
                cortes_optimos = fetch_cached_results(args.db, cached_id[0]) # Recargamos para incluir los nuevos
        else:
            cortes_optimos = encontrar_cortes_optimos(pliego_cm, minimo_cm, maximo_cm, args.incremento, cortes_forzados_cm)
            # Guardamos el análisis completo, incluso si tiene cortes forzados, para cachearlo para el futuro.
            if cortes_optimos:
                guardar_analisis_completo(args.db, pliego_cm, minimo_cm, maximo_cm, args.incremento, cortes_optimos)

        if cortes_optimos:
            if not args.no_pdf:
                pdf_dir = "layouts_pdf"; os.makedirs(pdf_dir, exist_ok=True)
                print("\n--- Generando PDFs de los Cortes Óptimos ---")
                for corte in cortes_optimos:
                    piezas, layout = calcular_cortes_custom(pliego_cm[0], pliego_cm[1], corte['ancho'], corte['alto'])
                    filename = os.path.join(pdf_dir, f"Corte_{int(pliego_cm[0]*10)}x{int(pliego_cm[1]*10)}_{int(corte['ancho']*10)}x{int(corte['alto']*10)}.pdf")
                    generar_pdf_layout(pliego_cm, (corte['ancho'], corte['alto']), piezas, layout, filename)

            print("\n--- Resumen de Cortes Óptimos Encontrados ---")
            for piezas, grupo in groupby(sorted(cortes_optimos, key=lambda x: x['piezas'], reverse=True), key=lambda x: x['piezas']):
                print(f"\nCortes que rinden {piezas} piezas por pliego:")
                for c in sorted(list(grupo), key=lambda x: (x['ancho'], x['alto'])):
                    print(f"  - {c['ancho']:.2f} x {c['alto']:.2f} cm")
