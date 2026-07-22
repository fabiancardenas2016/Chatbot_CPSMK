# -*- coding: utf-8 -*-
"""
config.py
---------
Configuración centralizada del backend. Reemplaza el uso de
`google.colab.userdata` del notebook original por variables de entorno
(carga desde un archivo .env con python-dotenv), lo cual permite ejecutar
el proyecto en cualquier máquina (local, servidor, contenedor) y no solo
en Google Colab.
"""

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

# Carga las variables definidas en el archivo .env (si existe) al entorno del proceso
load_dotenv()

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documentos"

# La librería `faiss` (usada para el índice vectorial) tiene un bug conocido en
# Windows: falla al escribir en rutas que contienen tildes/ñ u otros caracteres
# no-ASCII, algo común si el proyecto vive dentro de "OneDrive\...\María...".
# Por eso la carpeta del índice se puede redefinir con FAISS_INDEX_DIR en el
# .env, apuntando a una ruta simple como C:\rrhh_data\faiss_index. Si no se
# define, se usa la ruta por defecto dentro del proyecto.
INDEX_DIR = DATA_DIR / "faiss_index" # solo usar si no se quiere usar la variable de entorno FAISS_INDEX_DIR o si no está definida o si en la ruta de almacenamiento no hay caracteres especiales (espacios, acentos, etc.) que puedan generar problemas en la ruta de la base vectorial.
# INDEX_DIR = Path(os.getenv("FAISS_INDEX_DIR", str(DATA_DIR / "faiss_index"))) # usar si la variable de entorno FAISS_INDEX_DIR está definida y en la ruta de almacenamiento hay caracteres especiales (espacios, acentos, etc.) que puedan generar problemas en la ruta de la base vectorial..   
LOGS_DIR = BACKEND_DIR / "logs"

DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Credenciales y modelos (usar siempre servicios de nivel gratuito)
# ---------------------------------------------------------------------------
# Clave de la API de Google AI Studio (gratuita). Se obtiene en:
# https://aistudio.google.com/apikey
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# Modelo de chat (gemini-2.5-flash / gemini-2.5-flash-lite están disponibles
# en el nivel gratuito de Google AI Studio). Se puede sobreescribir con la
# variable de entorno LLM_MODEL sin tocar el código.
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

# Modelo de embeddings gratuito de Google (reemplaza a text-embedding-004,
# que fue descontinuado). gemini-embedding-001 está disponible sin costo.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")

# ---------------------------------------------------------------------------
# Parámetros del RAG
# ---------------------------------------------------------------------------
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1600"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
RETRIEVER_SCORE_THRESHOLD = float(os.getenv("RETRIEVER_SCORE_THRESHOLD", "0.3"))
RETRIEVER_K = int(os.getenv("RETRIEVER_K", "4"))

# ---------------------------------------------------------------------------
# Servidor
# ---------------------------------------------------------------------------
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
# Orígenes permitidos para CORS (separados por coma). "*" habilita todos.
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def configurar_logging() -> logging.Logger:
    """Configura un logger compartido por toda la aplicación (consola + archivo)."""
    logger = logging.getLogger("rrhh_chatbot")
    if logger.handlers:  # evita handlers duplicados si se llama más de una vez
        return logger

    logger.setLevel(LOG_LEVEL)
    formato = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    consola_handler = logging.StreamHandler()
    consola_handler.setFormatter(formato)
    logger.addHandler(consola_handler)

    archivo_handler = logging.FileHandler(LOGS_DIR / "backend.log", encoding="utf-8")
    archivo_handler.setFormatter(formato)
    logger.addHandler(archivo_handler)

    return logger


def validar_configuracion() -> None:
    """Valida que la configuración mínima esté presente antes de arrancar la app."""
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY no está definida. Copia '.env.example' a '.env' y "
            "coloca tu clave gratuita de Google AI Studio "
            "(https://aistudio.google.com/apikey)."
        )
