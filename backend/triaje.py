# -*- coding: utf-8 -*-
"""
triaje.py
---------
Clasifica el mensaje del usuario en una de tres acciones:
AUTO_RESOLVER, PEDIR_INFO o ABRIR_TICKET. Adaptado del notebook original
(sección "System Prompt"), usando `with_structured_output` para forzar
una salida JSON validada por Pydantic (TriajeOut).

Nota de robustez: en algunas versiones recientes de langchain-google-genai,
`with_structured_output` puede devolver `None` (en vez de lanzar una
excepción) cuando el modelo no invoca correctamente la herramienta interna
de "function calling". Por eso `clasificar()` reintenta un par de veces y,
si sigue fallando, recurre a un modo de respaldo: le pide al LLM el JSON en
texto plano y lo parsea manualmente con Pydantic.
"""

import json
from typing import Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import ValidationError

from config import LLM_MODEL, LLM_TEMPERATURE, GOOGLE_API_KEY, configurar_logging
from models import TriajeOut

logger = configurar_logging()

PROMPT_TRIAJE = """
Eres un especialista en triaje de la CAJA DE PREVISIÓN SOCIAL MUNICIPAL DE BUCARAMANGA
para el departamento de Recursos Humanos.
Dado el mensaje del usuario, devuelve SÓLO un JSON con:

{
    "decision": "AUTO_RESOLVER" | "PEDIR_INFO" | "ABRIR_TICKET",
    "urgencia": "BAJA" | "MEDIANA" | "ALTA",
    "campos_faltantes": ["..."]
}

Reglas:
- AUTO_RESOLVER: Preguntas claras sobre las situaciones administrativas que podrían
  presentarse en el quehacer del objetivo misional de la Caja de Previsión Social
  Municipal de Bucaramanga (Ej.: "¿Cuáles licencias puedo solicitar?").
- PEDIR_INFO: Mensajes imprecisos o para los cuales no haya información para dar
  respuesta en los textos proporcionados, o sin contexto suficiente para identificar
  el tema (Ej.: "Necesito ayuda con una política" o preguntas ajenas a RR.HH.).
- ABRIR_TICKET: Solicitudes de licencias, permisos, nombramientos, vacaciones, o
  cuando el usuario solicita explícitamente abrir un ticket
  (Ej.: "Quiero una excepción para trabajar remotamente durante 5 días").

Analiza el mensaje y decide la acción más adecuada.
"""

PROMPT_TRIAJE_JSON_PLANO = (
    PROMPT_TRIAJE
    + "\n\nIMPORTANTE: responde ÚNICAMENTE con el objeto JSON, sin explicaciones, "
    "sin texto adicional y sin usar bloques de código (```)."
)

FALLBACK_TRIAJE: Dict = {
    "decision": "PEDIR_INFO",
    "urgencia": "BAJA",
    "campos_faltantes": ["No fue posible clasificar el mensaje automáticamente"],
}

MAX_INTENTOS_ESTRUCTURADO = 2


def _crear_llm_triaje() -> ChatGoogleGenerativeAI:
    """Crea (una sola vez, vía caché del llamador) el LLM configurado para triaje."""
    return ChatGoogleGenerativeAI(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        google_api_key=GOOGLE_API_KEY,
    )


def _extraer_texto(contenido) -> str:
    """
    Normaliza `AIMessage.content` a texto plano.

    En versiones recientes de langchain-google-genai (modelos Gemini 3.x),
    el contenido puede llegar como una lista de "bloques" en vez de un string
    simple, por ejemplo: [{"type": "text", "text": "..."}]. Esta función
    soporta ambos formatos.
    """
    if isinstance(contenido, str):
        return contenido

    if isinstance(contenido, list):
        partes = []
        for bloque in contenido:
            if isinstance(bloque, str):
                partes.append(bloque)
            elif isinstance(bloque, dict):
                partes.append(str(bloque.get("text", bloque.get("content", ""))))
        return "".join(partes)

    return str(contenido) if contenido is not None else ""


def _limpiar_json_texto(texto: str) -> str:
    """Quita posibles cercos de código (```json ... ```) alrededor del JSON."""
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("```", 2)[1] if texto.count("```") >= 2 else texto.strip("`")
        texto = texto.removeprefix("json").strip()
    return texto.strip()


class ServicioTriaje:
    """Encapsula el LLM y la cadena de salida estructurada para el triaje."""

    def __init__(self) -> None:
        self._llm = _crear_llm_triaje()
        self._chain = self._llm.with_structured_output(TriajeOut)

    def _intentar_salida_estructurada(self, mensaje: str) -> Optional[TriajeOut]:
        """Intenta obtener el triaje vía with_structured_output (tool calling)."""
        for intento in range(1, MAX_INTENTOS_ESTRUCTURADO + 1):
            try:
                salida = self._chain.invoke(
                    [
                        SystemMessage(content=PROMPT_TRIAJE),
                        HumanMessage(content=mensaje),
                    ]
                )
                if salida is not None:
                    return salida
                logger.warning(
                    "Intento %d/%d: el LLM no devolvió una salida estructurada "
                    "válida (None) para: %s",
                    intento,
                    MAX_INTENTOS_ESTRUCTURADO,
                    mensaje,
                )
            except Exception:
                logger.exception(
                    "Intento %d/%d fallido en el triaje estructurado para: %s",
                    intento,
                    MAX_INTENTOS_ESTRUCTURADO,
                    mensaje,
                )
        return None

    def _intentar_fallback_json_plano(self, mensaje: str) -> Optional[TriajeOut]:
        """Respaldo: pide el JSON como texto plano y lo parsea manualmente."""
        try:
            respuesta = self._llm.invoke(
                [
                    SystemMessage(content=PROMPT_TRIAJE_JSON_PLANO),
                    HumanMessage(content=mensaje),
                ]
            )
            texto = _limpiar_json_texto(_extraer_texto(respuesta.content))
            logger.debug("Texto crudo del respaldo de triaje: %r", texto)

            try:
                datos = json.loads(texto)
            except json.JSONDecodeError:
                # El modelo pudo haber agregado texto antes/después del JSON
                # a pesar de la instrucción; se intenta extraer solo el bloque {...}.
                inicio, fin = texto.find("{"), texto.rfind("}")
                if inicio == -1 or fin == -1 or fin < inicio:
                    raise
                datos = json.loads(texto[inicio : fin + 1])

            return TriajeOut(**datos)
        except (json.JSONDecodeError, ValidationError):
            logger.exception(
                "El respaldo de triaje (JSON en texto plano) no pudo parsearse para: %s",
                mensaje,
            )
        except Exception:
            logger.exception(
                "Error inesperado en el respaldo de triaje para: %s", mensaje
            )
        return None

    def clasificar(self, mensaje: str) -> Dict:
        """Clasifica `mensaje` y retorna un dict con decision/urgencia/campos_faltantes."""
        salida = self._intentar_salida_estructurada(mensaje)

        if salida is None:
            logger.info("Usando el respaldo de JSON en texto plano para: %s", mensaje)
            salida = self._intentar_fallback_json_plano(mensaje)

        if salida is not None:
            return salida.model_dump()

        logger.error(
            "Triaje agotó todos los intentos (estructurado y respaldo) para: %s. "
            "Se usará PEDIR_INFO por defecto.",
            mensaje,
        )
        return dict(FALLBACK_TRIAJE)


# Instancia única reutilizada por toda la aplicación (evita recrear el cliente LLM
# en cada petición HTTP).
_servicio_triaje: ServicioTriaje | None = None


def obtener_servicio_triaje() -> ServicioTriaje:
    global _servicio_triaje
    if _servicio_triaje is None:
        _servicio_triaje = ServicioTriaje()
    return _servicio_triaje


def triaje(mensaje: str) -> Dict:
    """Punto de entrada simple usado por el resto del backend (agent.py)."""
    return obtener_servicio_triaje().clasificar(mensaje)

