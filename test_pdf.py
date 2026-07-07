import fitz
import io
from barcode import Code128
from barcode.writer import ImageWriter

doc = fitz.open()
page = doc.new_page()

buffer = io.BytesIO()
Code128("S00123", writer=ImageWriter()).write(buffer, options={'write_text': False})
buffer.seek(0)
barcode_rect = fitz.Rect(10, 10, 200, 50)
try:
    page.insert_image(barcode_rect, stream=buffer)
    print("Stream buffer WORKED")
except Exception as e:
    print("Error with stream=buffer:", e)

doc.save("test_pdf.pdf")
doc.close()
