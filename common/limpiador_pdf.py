import fitz  # PyMuPDF
import argparse
import os

def limpiar_pdf(input_path, output_path):
    """
    Abre un PDF, copia sus páginas a un nuevo PDF y lo guarda,
    realizando una limpieza y reescritura de la estructura interna.
    Esto puede solucionar problemas de renderizado o impresión.
    """
    try:
        print(f"Abriendo PDF de entrada: {input_path}")
        doc_src = fitz.open(input_path)
        doc_clean = fitz.open()  # Crea un nuevo documento PDF vacío

        for i, page_src in enumerate(doc_src):
            print(f"Procesando página {i + 1}/{len(doc_src)}...")
            # Crea una nueva página en el documento limpio con las mismas dimensiones
            page_clean = doc_clean.new_page(width=page_src.rect.width, height=page_src.rect.height)
            # Inserta el contenido de la página original en la nueva página
            page_clean.show_pdf_page(page_clean.rect, doc_src, i)
        
        print(f"Guardando PDF limpio en: {output_path}")
        # Guarda el nuevo documento con opciones de limpieza y deflación
        doc_clean.save(output_path, garbage=4, deflate=True, clean=True)
        
        doc_src.close()
        doc_clean.close()
        print("Proceso de limpieza de PDF completado exitosamente.")
        print(f"El archivo limpio se encuentra en: {output_path}")

    except Exception as e:
        print(f"Error durante el proceso de limpieza del PDF: {e}")
        if 'doc_src' in locals() and doc_src.is_closed == False:
            doc_src.close()
        if 'doc_clean' in locals() and doc_clean.is_closed == False:
            doc_clean.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limpia y reescribe un archivo PDF para solucionar posibles problemas de impresión.")
    parser.add_argument("--input", required=True, help="Ruta al archivo PDF de entrada a limpiar.")
    parser.add_argument("--output", required=True, help="Ruta donde se guardará el archivo PDF limpio.")
    
    args = parser.parse_args()

    # Asegúrate de que la ruta de salida sea absoluta
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    limpiar_pdf(args.input, args.output)
