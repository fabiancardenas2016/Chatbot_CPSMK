# -*- coding: utf-8 -*-
"""
app.py
------
Punto de entrada del backend. Expone una API REST (FastAPI) que el frontend
consume vía JavaScript (fetch) y, además, sirve los archivos estáticos del
frontend para que todo el proyecto pueda desplegarse como un único servicio.

Ejecutar en desarrollo:
    uvicorn app:app --reload --host 0.0.0.0 --port 8000

Ejecutar en producción:
    uvicorn app:app --host 0.0.0.0 --port 8000 --workers 2
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agent import invocar_agente
from config import CORS_ORIGINS, configurar_logging, validar_configuracion
from models import ErrorResponse, PreguntaRequest, RespuestaResponse
from rag import obtener_servicio_rag

logger = configurar_logging()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Valida configuración e inicializa el índice RAG al arrancar el servidor."""
    logger.info("Iniciando backend del chatbot de RR.HH....")
    try:
        validar_configuracion()
        obtener_servicio_rag()  # construye o carga el índice FAISS
        logger.info("Backend listo para recibir peticiones.")
    except Exception:
        logger.exception("Error inicializando el backend")
        raise
    yield
    logger.info("Apagando backend.")


app = FastAPI(
    title="Chatbot RR.HH. - Caja de Previsión Social Municipal de Bucaramanga",
    description=(
        "API para el asistente virtual de Recursos Humanos, basado en RAG "
        "sobre los manuales internos de la entidad."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/salud", tags=["sistema"])
def salud():
    """Endpoint simple para verificar que el backend está activo (health check)."""
    return {"estado": "ok"}


@app.post(
    "/api/preguntar",
    response_model=RespuestaResponse,
    responses={500: {"model": ErrorResponse}},
    tags=["chat"],
)
def preguntar(payload: PreguntaRequest):
    """Recibe una pregunta del frontend, la procesa con el agente y retorna la respuesta."""
    pregunta = payload.pregunta.strip()
    logger.info("Pregunta recibida: %s", pregunta)

    if not pregunta:
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")

    try:
        resultado = invocar_agente(pregunta)
        return RespuestaResponse(**resultado)
    except Exception:
        logger.exception("Error procesando la pregunta: %s", pregunta)
        raise HTTPException(
            status_code=500,
            detail="Ocurrió un error procesando tu pregunta. Intenta nuevamente en unos minutos.",
        )


# Sirve el frontend (HTML/CSS/JS) como archivos estáticos en la raíz "/".
# Debe montarse después de las rutas de la API para que /api/* tenga prioridad.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
