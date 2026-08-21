#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mapeo de Operaciones de Odoo a Estados de BMG
==============================================

Este archivo define la relación entre las operaciones de fabricación en Odoo
y los estados que deben notificarse a la API de BMG.

Estructura:
-----------
Cada operación tiene:
- nombre_operacion_odoo: Nombre que identifica la operación en Odoo
- estado_disponible: Estado BMG cuando la operación está lista para empezar (opcional)
- estado_en_progreso: Estado BMG cuando se marca como "En Progreso" (opcional)
- estado_completado: Estado BMG cuando se marca como "Hecho" (requerido)

Estados segón tipo de pedido:
- POD: Print on Demand (pedidos normales de Bibliomanager)
- eDist: Pedidos de distribución

Notas:
------
- Si un estado es None, significa que NO se debe notificar a BMG en ese momento
- Todas las operaciones DEBEN tener al menos estado_completado
"""

# ============================================================================
# MAPEO COMPLETO DE ESTADOS BMG (ID <-> Nombre)
# ============================================================================

BMG_STATUS_MAP = {
    0: "Ingresado sin confimar",
    1: "PRESUPUESTO PENDIENTE",
    2: "PRESUPUESTO ENVIADO",
    3: "PRESUPUESTO RECHAZADO",
    4: "PENDIENTE DE ORIGINAL",
    5: "ARCHIVOS RECIBIDOS WEB",
    6: "ARCHIVOS RECIBIDOS MEDIOS FÍSICOS",
    7: "ARCHIVOS RECIBIDOS E-MAIL",
    8: "ARCHIVOS RECIBIDOS FTP",
    9: "EN VALIDACIÓN",
    10: "MUESTRA DIGITAL",
    11: "MUESTRA A PRODUCIR",
    12: "MUESTRA PRODUCIDA",
    13: "MUESTRA ENVIADA",
    14: "MUESTRA APROBADA",
    15: "MUESTRA RECHAZADA",
    16: "IMPOSICIÓN PENDIENTE",
    17: "PRIMERA IMPRESIÓN",
    18: "REIMPRESIÓN PENDIENTE",
    19: "Producción coordinada",
    20: "Tapa Guillotinada",
    21: "Tapa Laminada",
    22: "Pendiente de Encuadernar",
    23: "Encuadernando",
    24: "Encuadernado finalizado",
    25: "Producido",
    26: "Realizado Guillotinado Final",
    27: "EN PROCESO DE ENVÍO",
    28: "COORDINACIÓN PAGOS",
    29: "PAGO CONFIRMADO",
    30: "RETENIDO",
    31: "LOGÍSTICA ESPECIAL",
    32: "ENVIADO",
    33: "DEVUELTO",
    34: "INCIDENCIA",
    35: "INCIDENCIA RESPONDIDA",
    36: "RECLAMO CLIENTE WEB",
    37: "RECLAMO CLIENTE INTERNO",
    38: "ANULADO",
    39: "CONSULTA INTERNA",
    40: "RESPUESTA INTERNA",
    41: "CONSULTA A COMERCIAL",
    42: "RESPUESTA DE COMERCIAL",
    43: "ENTREGADO",
    44: "PRESUPUESTO VENCIDO",
    45: "PEDIDO PLAZO VENCIDO",
    46: "ANTICIPO PENDIENTE",
    47: "ANTICIPO RECIBIDO",
    48: "TAPA PROVISTA PENDIENTE",
    49: "Tapa Impresa",
    51: "Interior Guillotinado",
    52: "En Embalaje",
    53: "FACTURADO",
    59: "En Impresión Interior ByN",
    60: "En Impresión Interior Color",
    61: "Interior ByN Impreso",
    63: "Interior Color Impreso",
    99: "INCIDENCIA INTERNA"
}

BMG_STATUS_NAME_TO_ID = {v: k for k, v in BMG_STATUS_MAP.items()}

def get_bmg_status_name(status_id):
    """Obtiene el nombre de un estado BMG dado su ID."""
    return BMG_STATUS_MAP.get(status_id, "Estado Desconocido")

def get_bmg_status_id(status_name):
    """Obtiene el ID de un estado BMG dado su nombre."""
    return BMG_STATUS_NAME_TO_ID.get(status_name)

# ============================================================================
# MAPEO DE OPERACIONES A ESTADOS BMG
# ============================================================================

MAPEO_ESTADOS_BMG = {
    
    # ------------------------------------------------------------------------
    # IMPRESIÓN INTERIOR B/N
    # ------------------------------------------------------------------------
    'IMPRIMIR_INTERIOR_BYN': {
        'nombre_operacion_odoo': 'Imprimir Interior',  # Nombre en la operación de Odoo
        'descripcion': 'Impresión del interior en blanco y negro',
        'estado_disponible': None,  # No se notifica cuando está disponible
        'estado_en_progreso': {
            'POD': 59,   # En Impresión Interior ByN (POD)
            'eDist': 101 # En Producción (eDist)
        },
        'estado_completado': {
            'POD': 61,   # Interior ByN Impreso (POD)
            'eDist': 103 # Impresión Contenido (eDist)
        }
    },
    
    # ------------------------------------------------------------------------
    # IMPRESIÓN INTERIOR COLOR
    # ------------------------------------------------------------------------
    'IMPRIMIR_INTERIOR_COLOR': {
        'nombre_operacion_odoo': 'Imprimir Interior Color',
        'descripcion': 'Impresión del interior a color',
        'estado_disponible': None,
        'estado_en_progreso': {
            'POD': 60,   # En Impresión Interior Color (POD)
            'eDist': 101 # En Producción (eDist)
        },
        'estado_completado': {
            'POD': 63,   # Interior Color Impreso (POD)
            'eDist': 103 # Impresión Contenido (eDist)
        }
    },
    
    # ------------------------------------------------------------------------
    # IMPRESIÓN DE TAPA
    # ------------------------------------------------------------------------
    'IMPRIMIR_TAPA': {
        'nombre_operacion_odoo': 'Imprimir Tapa',
        'descripcion': 'Impresión de tapas',
        'estado_disponible': None,
        'estado_en_progreso': None,  # No se informa cuando se está imprimiendo
        'estado_completado': {
            'POD': 49,   # Tapa Impresa (POD)
            'eDist': 102 # Impresión Tapa (eDist)
        }
    },
    
    # ------------------------------------------------------------------------
    # LAMINADO DE TAPA
    # ------------------------------------------------------------------------
    'LAMINAR_TAPA': {
        'nombre_operacion_odoo': 'Laminar',
        'descripcion': 'Laminado de tapas',
        'estado_disponible': None,
        'estado_en_progreso': None,  # No se informa cuando se está laminando
        'estado_completado': {
            'POD': 21,   # Tapa Laminada (POD)
            'eDist': 109 # Tapa Laminada (eDist)
        }
    },
    
    # ------------------------------------------------------------------------
    # GUILLOTINADO DE TAPA (solo pedidos viejos, estructura pre-2026-08-21 -
    # las OF nuevas ya no tienen esta operacion, ver GUILLOTINAR_TAPA_INTERIOR
    # mas abajo. Se deja esta entrada para que las OF ya abiertas con la
    # estructura vieja sigan funcionando sin cambios hasta cerrarse.)
    # ------------------------------------------------------------------------
    'GUILLOTINAR_TAPA': {
        'nombre_operacion_odoo': 'Guillotinar Tapa',
        'descripcion': 'Guillotinado de tapas',
        'estado_disponible': None,
        'estado_en_progreso': None,
        'estado_completado': {
            'POD': 20,   # Tapa Guillotinada (POD)
            'eDist': None # No se notifica en eDist
        }
    },

    # ------------------------------------------------------------------------
    # GUILLOTINADO DE INTERIOR (B/N y COLOR juntos) - solo pedidos viejos,
    # ver mismo comentario que arriba.
    # ------------------------------------------------------------------------
    'GUILLOTINAR_INTERIOR': {
        'nombre_operacion_odoo': 'Guillotinar Interior',
        'descripcion': 'Guillotinado del interior (B/N y Color intercalados)',
        'estado_disponible': None,
        'estado_en_progreso': None,
        'estado_completado': {
            'POD': 51,   # Interior Guillotinado (POD)
            'eDist': 104 # Primer Corte (eDist)
        }
    },

    # ------------------------------------------------------------------------
    # GUILLOTINADO COMBINADO DE TAPA E INTERIOR (FIX 2026-08-21) - pedidos
    # nuevos: reemplaza a GUILLOTINAR_TAPA + GUILLOTINAR_INTERIOR por un solo
    # corte, hecho despues de Juntar. A pedido del usuario, dispara SOLO el
    # estado "Interior Guillotinado" hacia BMG (el de tapa no le importa a
    # BMG) - por eso usa los mismos estados que GUILLOTINAR_INTERIOR de
    # arriba.
    # ------------------------------------------------------------------------
    'GUILLOTINAR_TAPA_INTERIOR': {
        'nombre_operacion_odoo': 'Guillotinar Tapa e Interior',
        'descripcion': 'Guillotinado combinado de tapa e interior ya juntados',
        'estado_disponible': None,
        'estado_en_progreso': None,
        'estado_completado': {
            'POD': 51,   # Interior Guillotinado (POD) - mismo estado que GUILLOTINAR_INTERIOR
            'eDist': 104 # Primer Corte (eDist) - mismo estado que GUILLOTINAR_INTERIOR
        }
    },
    
    # ------------------------------------------------------------------------
    # JUNTAR TAPAS E INTERIOR (ALZADO/COMPAGINADO)
    # ------------------------------------------------------------------------
    'JUNTAR_TAPAS_INTERIOR': {
        'nombre_operacion_odoo': 'Juntar Tapas e Interior',
        'descripcion': 'Alzado - juntar interior con tapas',
        'estado_disponible': None,
        'estado_en_progreso': None,
        'estado_completado': {
            'POD': 22,   # Pendiente de Encuadernar (POD)
            'eDist': 105 # Compaginado (eDist)
        }
    },
    
    # ------------------------------------------------------------------------
    # ENCUADERNADO
    # ------------------------------------------------------------------------
    'ENCUADERNAR': {
        'nombre_operacion_odoo': 'Encuadernar',
        'descripcion': 'Encuadernado del libro',
        'estado_disponible': None,
        'estado_en_progreso': {
            'POD': 23,   # Encuadernando (POD)
            'eDist': None  # Encuadernando (eDist) - Mismo estado
        },
        'estado_completado': {
            'POD': 24,   # Encuadernado finalizado (POD)
            'eDist': 106 # Encuadernado (eDist)
        }
    },
    
    # ------------------------------------------------------------------------
    # GUILLOTINADO FINAL (REFILADO)
    # ------------------------------------------------------------------------
    'GUILLOTINADO_FINAL': {
        'nombre_operacion_odoo': 'Guillotinado Final',
        'descripcion': 'Refilado final del libro',
        'estado_disponible': None,
        'estado_en_progreso': {
            'POD': 26,   # Realizado Guillotinado Final (POD)
            'eDist': 107 # Refilado (eDist)
        },
        'estado_completado': {
            'POD': 52,   # En Embalaje (POD)
            'eDist': 107 # Refilado (eDist) - Mismo que en progreso
        }
    },
    
    # ------------------------------------------------------------------------
    # EMPAQUETADO
    # ------------------------------------------------------------------------
    'EMPACAR': {
        'nombre_operacion_odoo': 'Empacar',
        'descripcion': 'Empaquetado final',
        'estado_disponible': None,
        'estado_en_progreso': None,
        'estado_completado': {
            'POD': 25,   # Producido (POD)
            'eDist': 108 # Producido (eDist)
        }
    },
}


# ============================================================================
# ESTADOS DE LOGÍSTICA (No relacionados con fabricación)
# ============================================================================

ESTADOS_LOGISTICA_BMG = {
    'EN_PROCESO_ENVIO': {
        'POD': 27,
        'eDist': 200
    },
    'ENVIADO': {
        'POD': 32,
        'eDist': 202
    },
    'DISPONIBLE_RETIRAR': {
        'POD': None,  # No aplica para POD
        'eDist': 203
    },
    'ENTREGADO': {
        'POD': 43,
        'eDist': 204
    },
    'FACTURADO': {
        'POD': 53,
        'eDist': 205
    }
}


# ============================================================================
# ESTADOS INICIALES
# ============================================================================

ESTADOS_INICIALES_BMG = {
    'PRODUCCION_COORDINADA': {
        'POD': 19,   # Producción coordinada (POD)
        'eDist': 100 # Producción Pendiente (eDist)
    }
}


# ============================================================================
# ESTADOS FINALES (TERMINALES)
# ============================================================================
# Lista de IDs que indican que el ciclo de vida del pedido en BMG ha terminado.
# Incluye Entregado, Facturado y Anulado tanto para POD como para eDist.
LISTA_ESTADOS_FINALES_IDS = [
    BMG_STATUS_NAME_TO_ID.get('ENTREGADO'),
    BMG_STATUS_NAME_TO_ID.get('FACTURADO'),
    BMG_STATUS_NAME_TO_ID.get('ANULADO'),
    ESTADOS_LOGISTICA_BMG['ENTREGADO']['eDist'],
    ESTADOS_LOGISTICA_BMG['FACTURADO']['eDist']
]
# Limpiar valores None
LISTA_ESTADOS_FINALES_IDS = [id for id in LISTA_ESTADOS_FINALES_IDS if id is not None]

# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def obtener_estado_bmg(operacion_key, momento, tipo_pedido):
    """
    Obtiene el código de estado BMG para una operación específica.
    
    Args:
        operacion_key (str): Clave de la operación (ej: 'IMPRIMIR_INTERIOR_BYN')
        momento (str): 'disponible', 'en_progreso', o 'completado'
        tipo_pedido (str): 'POD' o 'eDist'
    
    Returns:
        int or None: Código de estado BMG, o None si no aplica
    
    Ejemplo:
        >>> obtener_estado_bmg('IMPRIMIR_INTERIOR_BYN', 'en_progreso', 'POD')
        59
    """
    if operacion_key not in MAPEO_ESTADOS_BMG:
        return None
    
    operacion = MAPEO_ESTADOS_BMG[operacion_key]
    campo_momento = f'estado_{momento}'
    
    if campo_momento not in operacion or operacion[campo_momento] is None:
        return None
    
    estados = operacion[campo_momento]
    
    if isinstance(estados, dict):
        return estados.get(tipo_pedido)
    
    return estados


def obtener_operacion_por_nombre_odoo(nombre_odoo):
    """
    Busca la clave de operación segón el nombre usado en Odoo.
    
    Args:
        nombre_odoo (str): Nombre de la operación en Odoo
    
    Returns:
        str or None: Clave de la operación o None si no se encuentra
    
    Ejemplo:
        >>> obtener_operacion_por_nombre_odoo('Imprimir Interior')
        'IMPRIMIR_INTERIOR_BYN'
    """
    for key, config in MAPEO_ESTADOS_BMG.items():
        if config['nombre_operacion_odoo'] == nombre_odoo:
            return key
    return None


def listar_operaciones_con_estado_en_progreso():
    """
    Retorna lista de operaciones que deben notificar cuando están en progreso.
    
    Returns:
        list: Lista de claves de operaciones
    """
    return [
        key for key, config in MAPEO_ESTADOS_BMG.items()
        if config['estado_en_progreso'] is not None
    ]


def debug_imprimir_mapeo():
    """Imprime el mapeo completo para debugging."""
    print("\n" + "="*80)
    print("MAPEO DE ESTADOS BMG")
    print("="*80)
    
    for key, config in MAPEO_ESTADOS_BMG.items():
        print(f"\n{key}:")
        print(f"  Nombre en Odoo: {config['nombre_operacion_odoo']}")
        print(f"  Descripción: {config['descripcion']}")
        
        if config['estado_disponible']:
            print(f"  Disponible: POD={config['estado_disponible'].get('POD', 'N/A')}, "
                  f"eDist={config['estado_disponible'].get('eDist', 'N/A')}")
        
        if config['estado_en_progreso']:
            print(f"  En Progreso: POD={config['estado_en_progreso'].get('POD', 'N/A')}, "
                  f"eDist={config['estado_en_progreso'].get('eDist', 'N/A')}")
        
        if config['estado_completado']:
            print(f"  Completado: POD={config['estado_completado'].get('POD', 'N/A')}, "
                  f"eDist={config['estado_completado'].get('eDist', 'N/A')}")


if __name__ == '__main__':
    # Test
    debug_imprimir_mapeo()
    
    print("\n" + "="*80)
    print("PRUEBAS")
    print("="*80)
    
    # Prueba 1
    estado = obtener_estado_bmg('IMPRIMIR_INTERIOR_BYN', 'en_progreso', 'POD')
    print(f"\nEstado al empezar impresión interior B/N (POD): {estado}")
    
    # Prueba 2
    estado = obtener_estado_bmg('IMPRIMIR_TAPA', 'en_progreso', 'POD')
    print(f"Estado al empezar impresión tapa (POD): {estado} (None = no se notifica)")
    
    # Prueba 3
    ops_con_progreso = listar_operaciones_con_estado_en_progreso()
    print(f"\nOperaciones que notifican 'en progreso': {ops_con_progreso}")