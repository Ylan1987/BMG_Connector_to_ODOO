# Usamos una imagen liviana de Python
FROM python:3.11-slim

# Instalar dependencias del sistema necesarias para procesamiento de PDF y API
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt-dev \
    python3-dev \
    libmupdf-dev \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requerimientos e instalar dependencias primero (cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del proyecto
COPY . .

# Comando para ejecutar el orquestador en un bucle infinito cada 10 min
# El flag -u asegura que los logs se vean en tiempo real en QNAP
CMD ["python", "-u", "-c", "import time, subprocess; \
while True: \
    print('--- 🚀 Iniciando ejecución automática (Cada 10 min) ---'); \
    subprocess.run(['python', '00_orquestador.py']); \
    print('--- 😴 Ciclo finalizado. Esperando 10 minutos... ---'); \
    time.sleep(600)"]
