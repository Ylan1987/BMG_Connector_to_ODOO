import fitz
try:
    doc = fitz.open("test_pdf.pdf")
    print("PDF is valid. Page count:", doc.page_count)
except Exception as e:
    print("PDF is invalid:", e)
