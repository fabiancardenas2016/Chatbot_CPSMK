# -*- coding: utf-8 -*-
"""
models.py
---------
Modelos Pydantic usados por la API (FastAPI) y por el agente interno.
Sirven tanto para validar la entrada del usuario como para dar una forma
JSON estable y documentada a la respuesta que consume el frontend.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TriajeOut(BaseModel):
    """Salida estructurada que el LLM debe devolver en el paso de triaje."""

    decision: Literal["AUTO_RESOLVER", "PEDIR_INFO", "ABRIR_TICKET"]
    urgencia: Literal["BAJA", "MEDIANA", "ALTA"]
    campos_faltantes: List[str] = Field(default_factory=list)


class PreguntaRequest(BaseModel):
    """Cuerpo esperado en POST /api/preguntar."""

    pregunta: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Pregunta del funcionario en lenguaje natural.",
        examples=["¿Cuándo puedo solicitar una licencia de maternidad?"],
    )


class Citacion(BaseModel):
    """Fragmento de documento usado para justificar una respuesta del RAG."""

    documento: str
    contenido: str


class RespuestaResponse(BaseModel):
    """Cuerpo de la respuesta que recibe el frontend."""

    pregunta: str
    respuesta: str
    decision: str
    urgencia: str
    accion_final: str
    citaciones: List[Citacion] = Field(default_factory=list)
    es_ticket: bool = False


class ErrorResponse(BaseModel):
    detalle: str
