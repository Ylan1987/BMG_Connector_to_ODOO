import csv
import re
import sqlite3
import subprocess
import os

DB_PATH = 'cortes_optimos.db'

def get_paper_info(row, headers):
    """Extrae la información relevante de una fila de CSV si es un producto de papel."""
    category_idx = headers.index('Categoría del producto/ID externo')
    if row[category_idx] == '__export__.product_category_materia_prima_papel':
        name_idx = headers.index('Nombre')
        name = row[name_idx]
        
        grammage_match = re.search(r'(\d+)gr', name)
        size_match = re.search(r'(\d+[.,]?\d*)\s*x\s*(\d+[.,]?\d*)cm', name)
        
        if grammage_match and size_match:
            grammage = grammage_match.group(1)
            width = float(size_match.group(1).replace(',', '.'))
            height = float(size_match.group(2).replace(',', '.'))
            return {
                'grammage': grammage,
                'width': width,
                'height': height,
                'original_name': name
            }
    return None

def check_cache(db_path, p, mi, ma, inc):
    """Verifica si un análisis ya existe en la base de datos."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM analisis WHERE p_w=? AND p_h=? AND min_w=? AND min_h=? AND max_w=? AND max_h=? AND inc=?",
                       (p[0], p[1], mi[0], mi[1], ma[0], ma[1], inc))
        return cursor.fetchone()

def run_optimizer(pliego_cm):
    """Ejecuta el script optimizador_cortes.py si es necesario."""
    pliego_str = f"{pliego_cm[0]}x{pliego_cm[1]}"
    minimo_str = "15x21"
    maximo_str = pliego_str
    incremento_str = "0.1"
    
    print(f"Ejecutando optimizador para pliego {pliego_str}...")
    command = [
        'python', 'optimizador_cortes.py',
        '--pliego', pliego_str,
        '--minimo', minimo_str,
        '--maximo', maximo_str,
        '--incremento', incremento_str
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print("Optimizador ejecutado con éxito.")
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar el optimizador:")
        print(e.stdout)
        print(e.stderr)
        raise

def fetch_results(db_path, analisis_id):
    """Obtiene los resultados de cortes óptimos para un análisis dado."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT ancho, alto, piezas FROM resultados WHERE analisis_id = ?", (analisis_id, ))
        return [dict(row) for row in cursor.fetchall()]

def generate_child_product_row(parent_paper_info, cut_info):
    """Genera una fila para el CSV de producto hijo."""
    grammage = parent_paper_info['grammage']
    cut_width = cut_info['ancho']
    cut_height = cut_info['alto']
    
    # Formatear el nombre y el ID
    child_name = f"Papel Cortado {grammage}gr {cut_width}x{cut_height}cm"
    child_id_name = child_name.lower().replace(' ', '_').replace('.', '')
    child_id = f"__export__.product_template_{child_id_name}"

    return {
        'Categoría del producto/ID externo': '__export__.product_category_productos_intermedios_papel_cortado',
        'Nombre': child_name,
        'Categoría de la unidad de medida (no importar)': 'Hojas',
        'Unidad de medida (no importar)': 'Hoja',
        'UdM de compra (No importar)': 'Hoja',
        'Se puede comprar': 'FALSO',
        'Se puede vender': 'FALSO',
        'Product Type': 'Almacenable',
        'Política de facturación': 'Cantidades pedidas',
        'Etiquetas de la plantilla del producto': 'Pliego de impresión',
        'Rutas': 'Obtener Bajo Pedido (MTO),Fabricación',
        'Responsable': 'Andrea Fein',
        'Impuestos del cliente': 'IVA Ventas (22%)
',
        'Ubicación de producción': 'Virtual Locations/Production',
        'Ubicación de inventario': 'Virtual Locations/Inventory adjustment',
        'Id': child_id,
        'Unidad de medida/ID externo': '__export__.uom_uom_hojas_hoja',
        'UdM de compra/ID externo': '__export__.uom_uom_hojas_hoja',
    }

def main():
    """Función principal del script."""
    all_child_products = []
    try:
        with open('materia_prima.csv', mode='r', encoding='utf-8') as infile:
            reader = csv.reader(infile, delimiter='\t')
            headers = next(reader)
            
            for row in reader:
                if not row or len(row) < len(headers):
                    continue

                paper_info = get_paper_info(row, headers)
                if paper_info:
                    print(f"\nProcesando papel: {paper_info['original_name']}")
                    pliego_cm = (paper_info['width'], paper_info['height'])
                    minimo_cm = (15.0, 21.0)
                    maximo_cm = pliego_cm
                    incremento = 0.1

                    analisis_id_tuple = check_cache(DB_PATH, pliego_cm, minimo_cm, maximo_cm, incremento)
                    
                    if not analisis_id_tuple:
                        run_optimizer(pliego_cm)
                        analisis_id_tuple = check_cache(DB_PATH, pliego_cm, minimo_cm, maximo_cm, incremento)
                        if not analisis_id_tuple:
                            print(f"Error: No se pudo encontrar el análisis para {pliego_cm} después de ejecutar el optimizador.")
                            continue
                    
                    analisis_id = analisis_id_tuple[0]
                    print(f"Análisis encontrado con ID: {analisis_id}")
                    optimal_cuts = fetch_results(DB_PATH, analisis_id)
                    print(f"Se encontraron {len(optimal_cuts)} cortes óptimos.")

                    for cut in optimal_cuts:
                        child_product = generate_child_product_row(paper_info, cut)
                        all_child_products.append(child_product)

        if all_child_products:
            output_headers = list(all_child_products[0].keys())
            with open('productos_hijos.csv', mode='w', encoding='utf-8', newline='') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=output_headers, delimiter='\t')
                writer.writeheader()
                writer.writerows(all_child_products)
            print(f"\nSe ha generado el archivo 'productos_hijos.csv' con {len(all_child_products)} productos.")

    except FileNotFoundError:
        print(f"Error: No se encontró el archivo 'materia_prima.csv'.")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")

if __name__ == '__main__':
    main()
