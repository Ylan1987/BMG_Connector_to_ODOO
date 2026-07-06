# Generador de Cortes y Gestor de Papeles en Odoo

Este sub-proyecto contiene los scripts originales desarrollados para optimizar el corte de pliegos de papel y automatizar la creación de los "papeles cortados" (hijos) en Odoo. 

**Importante:** Estos scripts no se utilizan de forma activa en el orquestador principal (`V2.0`), pero se conservan como herramientas y para entender la lógica de negocio de cómo se estructuran los cortes en Odoo.

## 📁 Archivos Principales

- `optimizador_cortes.py`: Es el cerebro matemático. Recibe un tamaño de pliego (ej. 72x102) y busca todas las posibles combinaciones de corte iterando milímetro a milímetro. Guarda los resultados en caché para mayor velocidad.
- `cortes_optimos.db`: La base de datos (caché) donde el optimizador guarda los resultados de todos los cálculos previos.
- `generador_hijos_papel.py`: Lee el archivo CSV de materia prima, ejecuta el optimizador para cada papel madre, y genera un archivo `productos_hijos.csv` con los productos intermedios.
- `gestor_fabricacion_odoo.py`: Script que automatizaba la conexión con Odoo vía API para crear los productos padres, hijos y sus Listas de Materiales (LdM/BoM) directamente.
- `materia_prima.csv`: El archivo original exportado (o creado) con los papeles madre (incluye proveedores, precios, etc.).

## ⚠️ Problemas y Limitaciones Detectados

Durante la auditoría de estos scripts se detectaron fallas lógicas que explican por qué no deben usarse en producción sin correcciones:

1. **Creación de Papeles Madre sin Costos:**
   El script `gestor_fabricacion_odoo.py` cuenta con una función `ensure_product_exists`. Si detecta que un papel del CSV no existe en Odoo, **lo crea**, pero ignora completamente las columnas de Proveedor, Divisa y Precio del Excel. Esto deja a los papeles en Odoo con un costo de $0.
   *Solución manual recomendada:* Importar `materia_prima.csv` manualmente desde la interfaz de Odoo.

2. **LdM (BoM) Limitada a un Solo Pliego:**
   Cuando el script `gestor_fabricacion_odoo.py` intenta crear la LdM para un papel cortado (Ej. *Papel Obra 90gr 15x21cm*), verifica si ya existe una LdM para ese papel hijo. Si la encuentra, omite crear una nueva.
   *Problema:* Si el mismo papel cortado de 15x21 se puede sacar del pliego de 72x102 y también del de 65x95, el script **solo crea la LdM para el primero que procesa**. Esto genera que Odoo siempre mande a consumir el mismo pliego original, ignorando alternativas aunque haya stock.

## 🔧 ¿Cómo usar estas herramientas como apoyo?

Si necesitas recalcular algún layout o entender cuántos cortes entran en un papel, puedes usar el optimizador de forma independiente:

```bash
# Listar los análisis que ya están guardados en caché
python optimizador_cortes.py --listar-analisis

# Forzar el cálculo de un corte específico para un pliego
python optimizador_cortes.py --pliego 72x102 --agregar-corte 15x21
```

Este comando te arrojará cuántas piezas entran y además generará un PDF esquemático en la carpeta `layouts_pdf` mostrando cómo deben hacerse los cortes en la guillotina.
