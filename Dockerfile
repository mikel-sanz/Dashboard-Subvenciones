# Dockerfile optimizado para el despliegue del Dashboard de Subvenciones
FROM python:3.12-slim

# Evitar archivos .pyc en disco y forzar logs en consola sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

# Instalar librerías de sistema mínimas para Postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependencias e instalarlas limpiando caché
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar todo el código fuente del proyecto
COPY . .

# Exponer el puerto por defecto de Streamlit en contenedores
EXPOSE 8501

# Comando de arranque nativo de Streamlit
CMD ["python", "-m", "streamlit", "run", "src/visualization/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
