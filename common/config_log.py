# -*- coding: utf-8 -*-
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler

def setup_logging():
    """
    Configura el sistema de logging para que capture tanto los mensajes de 'logging'
    como los 'print' (stdout/stderr) en archivos físicos diarios.
    """
    # Evitar doble configuración si se importa varias veces
    if getattr(logging, "_bmg_setup_done", False):
        return
    
    # Directorio de logs (en la raíz del proyecto)
    # Intentamos usar /app/logs si existe (Docker), sino ./logs_sistema
    log_dir = "logs_sistema"
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except:
            log_dir = "." # Fallback al directorio actual

    log_file = os.path.join(log_dir, "sistema_bmg.log")
    
    # Formato con timestamp, nivel y nombre del script/logger
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s')

    # 1. Handler para archivo con rotación diaria (mantiene 30 días)
    try:
        file_handler = TimedRotatingFileHandler(
            log_file, when="midnight", interval=1, backupCount=30, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
    except Exception as e:
        print(f"No se pudo crear el manejador de archivos de log: {e}")
        file_handler = None

    # 2. Handler para consola (usando el stdout original para evitar bucles)
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    console_handler = logging.StreamHandler(original_stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Configurar el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Limpiar handlers previos (como los de basicConfig)
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    
    if file_handler:
        root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # --- Redirección de print() a logging ---
    class StreamToLogger:
        def __init__(self, logger_func, original_stream):
            self.logger_func = logger_func
            self.original_stream = original_stream

        def write(self, message):
            if message.strip():
                # Enviamos el mensaje al logger (que lo mandará al archivo y a la consola original)
                self.logger_func(message.strip())

        def flush(self):
            self.original_stream.flush()

    # Redirigimos sys.stdout y sys.stderr
    sys.stdout = StreamToLogger(logging.info, original_stdout)
    sys.stderr = StreamToLogger(logging.error, original_stderr)

    logging._bmg_setup_done = True
    logging.info(f"--- Logging inicializado (Archivo: {log_file}) ---")

# Ejecutar al importar
setup_logging()
