# -*- coding: utf-8 -*-
header = 'ID,Producto/ID externo,Nombre,Se puede vender,Se puede comprar,detailed_type,Política de facturación,Unidad de medida/ID externo,Categoria de la unidad de medida (No Importar),Unidad de medida (No Importar),UdM de compra/ID externo,UdM de compra (No Importar),Categoría del producto/ID externo,seller_ids/id,Proveedores/Proveedor,Proveedores/Divisa,Proveedores/Cantidad,Proveedores/Plazo de entrega,Proveedores/Precio\n'
for f_name in ['materia_prima_obra.csv', 'materia_prima_ahuesado.csv']:
    with open(f_name, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    with open(f_name, 'w', encoding='utf-8-sig', newline='') as f:
        f.write(header)
        f.write(lines[1])
