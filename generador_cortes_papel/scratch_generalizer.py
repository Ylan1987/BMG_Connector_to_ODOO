import sys
import os

with open(r'C:\Users\ylana\Downloads\BMG\V2.0\generador_cortes_papel\gestor_coteado.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace("open('materia_prima_coteado.csv', mode='r', encoding='utf-8')", "open(args.input_csv, mode='r', encoding='utf-8')")
code = code.replace("'materia_prima_coteado.csv'", "args.input_csv")
code = code.replace("parser.add_argument('--forzar-regeneracion'", "parser.add_argument('--input_csv', required=True, help='Archivo CSV de materia prima')\n    parser.add_argument('--forzar-regeneracion'")

with open(r'C:\Users\ylana\Downloads\BMG\V2.0\generador_cortes_papel\gestor_general.py', 'w', encoding='utf-8') as f:
    f.write(code)
