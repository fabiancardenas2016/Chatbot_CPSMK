# -*- coding: utf-8 -*-
"""
agent.py
--------
Define el grafo de estados (LangGraph) que orquesta el flujo completo:

    START -> triaje -> (auto_resolver | pedir_info | abrir_ticket) -> END

Es una adaptación directa de la sección "Agente con LangGraph" del notebook
original, extraída a un módulo independiente para que pueda ser invocada
desde la API (app.py) sin depender de Colab.
"""

from pathlib import Path
from typing import Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from config import configurar_logging
from rag import busqueda_de_respuestas_rag
from triaje import triaje

logger = configurar_logging()

# Palabras clave que, ante un fallo del RAG, sugieren que el caso debe
# derivarse a la apertura de un ticket en lugar de pedir más información.
KEYWORDS_ABRIR_TICKET = [
    "aprobación",
    "aprobar",
    "excepción",
    "liberación",
    "autorización",
    "autorizar",
    "abrir ticket",
    "acceso especial",
]


class AgentState(TypedDict, total=False):
    pregunta: str
    triaje: dict
    respuesta: Optional[str]
    citaciones: Optional[list]
    documentos_encontrados: Optional[bool]
    rag_exito: bool
    accion_final: str


# ---------------------------------------------------------------------------
# Nodos
# ---------------------------------------------------------------------------
def nodo_triaje(state: AgentState) -> AgentState:
    logger.info("Ejecutando nodo 'triaje' para: %s", state["pregunta"])
    return {"triaje": triaje(state["pregunta"])}


def nodo_auto_resolver(state: AgentState) -> AgentState:
    logger.info("Ejecutando nodo 'auto_resolver'")
    respuesta_rag = busqueda_de_respuestas_rag(state["pregunta"])

    update: AgentState = {
        "respuesta": respuesta_rag["respuesta"],
        "citaciones": respuesta_rag["citaciones"],
        "rag_exito": respuesta_rag["documentos_encontrados"],
    }
    update["accion_final"] = (
        "AUTO_RESOLVER" if respuesta_rag["documentos_encontrados"] else "PEDIR_INFO"
    )
    return update


def nodo_pedir_info(state: AgentState) -> AgentState:
    logger.info("Ejecutando nodo 'pedir_info'")
    return {
        "respuesta": (
            "Necesito más información sobre tu solicitud. ¿Podrías precisar el tema "
            "(por ejemplo: licencias, permisos, vacaciones, nombramientos) o dar más "
            "detalle de tu pregunta?"
        ),
        "citaciones": [],
        "accion_final": "PEDIR_INFO",
    }


def nodo_abrir_ticket(state: AgentState) -> AgentState:
    logger.info("Ejecutando nodo 'abrir_ticket'")
    tri = state["triaje"]
    return {
        "respuesta": (
            f"Se ha generado la solicitud de ticket con urgencia {tri['urgencia']}. "
            f"Pedido: {state['pregunta']}. Un funcionario del área de Recursos Humanos "
            "revisará tu caso a la brevedad."
        ),
        "citaciones": [],
        "accion_final": "ABRIR_TICKET",
    }


# ---------------------------------------------------------------------------
# Aristas condicionales
# ---------------------------------------------------------------------------
def arista_decision_triaje(state: AgentState) -> str:
    tri = state["triaje"]
    if tri["decision"] == "AUTO_RESOLVER":
        return "rag"
    if tri["decision"] == "PEDIR_INFO":
        return "info"
    return "ticket"


def arista_decision_rag(state: AgentState) -> str:
    if state["rag_exito"]:
        return "ok"

    if any(kw in state["pregunta"].lower() for kw in KEYWORDS_ABRIR_TICKET):
        return "ticket"

    return "info"


# ---------------------------------------------------------------------------
# Construcción del grafo
# ---------------------------------------------------------------------------
def construir_grafo():
    workflow = StateGraph(AgentState)

    workflow.add_node("triaje", nodo_triaje)
    workflow.add_node("auto_resolver", nodo_auto_resolver)
    workflow.add_node("pedir_info", nodo_pedir_info)
    workflow.add_node("abrir_ticket", nodo_abrir_ticket)

    workflow.add_edge(START, "triaje")
    workflow.add_conditional_edges(
        "triaje",
        arista_decision_triaje,
        {"rag": "auto_resolver", "info": "pedir_info", "ticket": "abrir_ticket"},
    )
    workflow.add_conditional_edges(
        "auto_resolver",
        arista_decision_rag,
        {"info": "pedir_info", "ticket": "abrir_ticket", "ok": END},
    )
    workflow.add_edge("pedir_info", END)
    workflow.add_edge("abrir_ticket", END)

    return workflow.compile()


# Grafo compilado una única vez y reutilizado en cada petición
_grafo = None


def obtener_grafo():
    global _grafo
    if _grafo is None:
        _grafo = construir_grafo()
    return _grafo


def invocar_agente(pregunta: str) -> Dict:
    """
    Ejecuta el flujo completo para `pregunta` y retorna un diccionario
    serializable en JSON (las citaciones se convierten de `Document` a dict).
    """
    grafo = obtener_grafo()
    resultado = grafo.invoke({"pregunta": pregunta})

    citaciones_serializadas: List[Dict] = []
    for cita in resultado.get("citaciones") or []:
        metadata = getattr(cita, "metadata", {}) or {}
        documento = metadata.get("file_path") or metadata.get("source") or "documento"
        citaciones_serializadas.append(
            {
                "documento": _nombre_archivo(documento),
                "contenido": cita.page_content.replace("\n", " ").strip(),
            }
        )

    tri = resultado.get("triaje", {})
    return {
        "pregunta": pregunta,
        "respuesta": resultado.get("respuesta", ""),
        "decision": tri.get("decision", ""),
        "urgencia": tri.get("urgencia", ""),
        "accion_final": resultado.get("accion_final", ""),
        "citaciones": citaciones_serializadas,
        "es_ticket": resultado.get("accion_final") == "ABRIR_TICKET",
    }


def _nombre_archivo(ruta: str) -> str:
    """Devuelve solo el nombre de archivo, evitando exponer rutas absolutas del servidor."""
    try:
        return Path(ruta).name
    except Exception:
        return ruta
