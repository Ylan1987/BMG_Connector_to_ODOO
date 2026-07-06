import csv
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

def main():
    backup_csv = 'materia_prima.bak.csv'
    if not os.path.exists(backup_csv):
        print(f"Error: No se encuentra {backup_csv}")
        return

    # 1. Leer el CSV gigante y agrupar por producto madre
    productos = []
    with open(backup_csv, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            if not row or len(row) < 3: continue
            
            # Crear un mini CSV por cada producto
            safe_name = row[2].replace(' ', '_').replace('.', '').replace('/', '_')
            mini_csv = f'materia_prima_{safe_name}.csv'
            
            with open(mini_csv, mode='w', encoding='utf-8', newline='') as out_f:
                writer = csv.writer(out_f)
                writer.writerow(headers)
                writer.writerow(row)
            
            productos.append({
                'nombre': row[2],
                'csv': mini_csv
            })

    print(f"Se generaron {len(productos)} archivos CSV individuales para los materiales madre.")
    print("Iniciando procesamiento en paralelo (Max 4 hilos para no saturar Odoo/Red)...")

    # 2. Función worker
    def procesar_producto(prod):
        csv_file = prod['csv']
        nombre = prod['nombre']
        print(f"[INICIO] Lanzando proceso para: {nombre}")
        
        # OJO: usando PYTHONUTF8=1 para no colgarse con los emojis ✅
        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'
        
        # Llamar al gestor_general.py pasándole el csv
        comando = ['python', 'gestor_general.py', '--input_csv', csv_file]
        try:
            proceso = subprocess.run(
                comando, 
                env=env,
                capture_output=True, 
                text=True
            )
            if proceso.returncode == 0:
                print(f"[EXITO] {nombre} finalizó correctamente.")
                return f"{nombre} - OK"
            else:
                print(f"[ERROR] {nombre} falló. Salida:\n{proceso.stderr}")
                return f"{nombre} - ERROR"
        except Exception as e:
            print(f"[EXCEPCION] {nombre} error al ejecutar: {e}")
            return f"{nombre} - EXCEPCION"

    # 3. Lanzar todo en paralelo
    MAX_WORKERS = 4
    resultados_ok = 0
    resultados_error = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futuros = {executor.submit(procesar_producto, p): p for p in productos}
        
        for futuro in as_completed(futuros):
            res = futuro.result()
            if "OK" in res:
                resultados_ok += 1
            else:
                resultados_error += 1

    print("\n--- RESUMEN FINAL ---")
    print(f"Total procesados: {len(productos)}")
    print(f"Exitosos: {resultados_ok}")
    print(f"Fallidos: {resultados_error}")
    print("---------------------")

if __name__ == '__main__':
    main()
