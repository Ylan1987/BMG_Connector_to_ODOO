import fitz # PyMuPDF
import argparse
import os

def inspect_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"Error: El archivo '{pdf_path}' no existe.")
        return

    try:
        doc = fitz.open(pdf_path)
        print(f"--- Analizando PDF: {pdf_path} ---")
        print(f"Número total de páginas: {doc.page_count}\n")

        for i in range(doc.page_count):
            page = doc[i]
            print(f"Página {i + 1}:")
            print(f"  MediaBox: {page.mediabox}")
            print(f"  CropBox: {page.cropbox}")
            print(f"  TrimBox: {page.trimbox}")
            print(f"  BleedBox: {page.bleedbox}")
            print(f"  ArtBox: {page.artbox}")
            print(f"  Rotación: {page.rotation} grados")
            print(f"  Matriz de Transformación: {page.transformation_matrix}")
            print("-" * 30)

        doc.close()

    except Exception as e:
        print(f"Error al procesar el PDF: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspecciona las cajas, rotación y matriz de transformación de cada página de un PDF.")
    parser.add_argument("--pdf", required=True, help="Ruta completa al archivo PDF a inspeccionar.")
    args = parser.parse_args()

    inspect_pdf(args.pdf)
