# -*- coding: utf-8 -*-
import sys

def compare_files(f1, f2):
    with open(f1, 'r', encoding='utf-8') as file1:
        lines1 = file1.readlines()
    with open(f2, 'r', encoding='utf-8') as file2:
        lines2 = file2.readlines()
    
    print(f"Comparando {f1} (Actual) vs {f2} (Original del Servidor)")
    print("-" * 50)
    
    # Simple check of unique lines in f1 that are not in f2
    unique_to_f1 = [l for l in lines1 if l not in lines2 and l.strip()]
    unique_to_f2 = [l for l in lines2 if l not in lines1 and l.strip()]
    
    print(f"Líneas agregadas o modificadas en {f1}:")
    for l in unique_to_f1:
        if len(l.strip()) > 0:
            print(f"+ {l.strip()}")
            
    print("\n" + "-" * 50)
    print(f"Líneas que estaban en {f2} pero fueron quitadas o cambiadas:")
    for l in unique_to_f2:
        if len(l.strip()) > 0:
            print(f"- {l.strip()}")

if __name__ == "__main__":
    compare_files('common/mapeosServer.py', 'common/mapeosServer2.py')
