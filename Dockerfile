# Imagen ligera y estable para producción
FROM python:3.11-slim

# Evita archivos .pyc y fuerza salida de logs sin buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema necesarias para pymupdf/faiss
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instala dependencias de Python primero (mejor cacheo de capas Docker)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r backend/requirements.txt

# Copia el resto del proyecto (backend + frontend)
COPY backend ./backend
COPY frontend ./frontend

WORKDIR /app/backend

EXPOSE 8000

# Healthcheck simple contra el endpoint de salud
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/salud')" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
