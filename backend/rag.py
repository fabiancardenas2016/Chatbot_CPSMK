# -*- coding: utf-8 -*-
"""
rag.py
------
Construye (o carga desde disco) el índice vectorial FAISS a partir de los
PDF de Recursos Humanos y expone `busqueda_de_respuestas_rag(pregunta)`,
que retorna la respuesta generada por el LLM junto con las citaciones
(fragmentos de documento) usadas como contexto.

Diferencias respecto del notebook original:
- Los documentos ya no se suben con `files.upload()` de Colab: se leen desde
  `backend/data/documentos/`.
- El índice FAISS se persiste en disco (`backend/data/faiss_index/`) para no
  tener que volver a generar embeddings (llamadas a la API) en cada arranque
  del servidor, lo cual ahorra cuota gratuita y tiempo de inicio.
- Se añadió manejo de errores y logging en cada etapa.
"""

from pathlib import Path
from typing import Dict, List

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

try:
    # Disponible en versiones recientes de langchain (langchain-classic)
    from langchain_classic.chains.combine_documents import create_stuff_documents_chain
except ImportError:  # pragma: no cover - alternativa según versión instalada
    from langchain.chains.combine_documents import create_stuff_documents_chain

from config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DOCUMENTS_DIR,
    EMBEDDING_MODEL,
    GOOGLE_API_KEY,
    INDEX_DIR,
    LLM_MODEL,
    LLM_TEMPERATURE,
    RETRIEVER_K,
    RETRIEVER_SCORE_THRESHOLD,
    configurar_logging,
)

logger = configurar_logging()

PROMPT_RAG = ChatPromptTemplate(
    [
        (
            "system",
            "Eres el especialista en RR.HH. de la CAJA DE PREVISIÓN SOCIAL MUNICIPAL "
            "DE BUCARAMANGA.\n"
            "Responde siempre en español, de forma clara y concisa, utilizando "
            "únicamente la información del contexto proporcionado.\n"
            "Si no hay información sobre la pregunta en el contexto, responde "
            "exactamente 'No lo sé'.",
        ),
        ("human", "Contexto: {context}\nPregunta del empleado: {input}"),
    ]
)


class ServicioRAG:
    """Encapsula el ciclo de vida del índice vectorial y la cadena de respuesta."""

    def __init__(self) -> None:
        self._llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            google_api_key=GOOGLE_API_KEY,
        )
        self._embeddings = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=GOOGLE_API_KEY,
        )
        self._document_chain = create_stuff_documents_chain(self._llm, PROMPT_RAG)
        self._vectorstore: FAISS | None = None
        self._retriever = None

    # ------------------------------------------------------------------
    # Construcción / carga del índice
    # ------------------------------------------------------------------
    def _cargar_documentos(self) -> List:
        pdfs = sorted(Path(DOCUMENTS_DIR).glob("*.pdf"))
        if not pdfs:
            raise FileNotFoundError(
                f"No se encontraron archivos PDF en {DOCUMENTS_DIR}. "
                "Coloca allí los documentos RRHH-1-Resumen.pdf ... RRHH-4-Resumen.pdf."
            )

        documentos = []
        for ruta in pdfs:
            try:
                loader = PyMuPDFLoader(str(ruta))
                documentos.extend(loader.load())
                logger.info("Documento cargado: %s", ruta.name)
            except Exception:
                logger.exception("Error cargando el archivo %s", ruta.name)
        logger.info("Total de páginas cargadas: %d", len(documentos))
        return documentos

    def _construir_indice(self) -> FAISS:
        documentos = self._cargar_documentos()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        chunks = splitter.split_documents(documentos)
        logger.info("Documentos divididos en %d fragmentos (chunks)", len(chunks))

        vectorstore = FAISS.from_documents(chunks, self._embeddings)
        vectorstore.save_local(str(INDEX_DIR))
        logger.info("Índice FAISS creado y guardado en %s", INDEX_DIR)
        return vectorstore

    def inicializar(self, forzar_reconstruccion: bool = False) -> None:
        """Carga el índice desde disco si existe; si no, lo construye desde los PDF."""
        indice_existe = (Path(INDEX_DIR) / "index.faiss").exists()

        if indice_existe and not forzar_reconstruccion:
            try:
                self._vectorstore = FAISS.load_local(
                    str(INDEX_DIR),
                    self._embeddings,
                    allow_dangerous_deserialization=True,
                )
                logger.info("Índice FAISS cargado desde disco (%s)", INDEX_DIR)
            except Exception:
                logger.exception("No se pudo cargar el índice existente, se reconstruirá")
                self._vectorstore = self._construir_indice()
        else:
            self._vectorstore = self._construir_indice()

        self._retriever = self._vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                "score_threshold": RETRIEVER_SCORE_THRESHOLD,
                "k": RETRIEVER_K,
            },
        )

    @property
    def listo(self) -> bool:
        return self._retriever is not None

    # ------------------------------------------------------------------
    # Búsqueda de respuestas
    # ------------------------------------------------------------------
    def buscar_respuesta(self, pregunta: str) -> Dict:
        """Ejecuta la búsqueda por similitud y genera la respuesta final del LLM."""
        if not self.listo:
            raise RuntimeError("El servicio RAG no ha sido inicializado.")

        try:
            documentos_relacionados = self._retriever.invoke(pregunta)
        except Exception:
            logger.exception("Error consultando el retriever para: %s", pregunta)
            documentos_relacionados = []

        if not documentos_relacionados:
            return {
                "respuesta": "No lo sé.",
                "citaciones": [],
                "documentos_encontrados": False,
            }

        try:
            respuesta = self._document_chain.invoke(
                {"input": pregunta, "context": documentos_relacionados}
            )
        except Exception:
            logger.exception("Error generando la respuesta RAG para: %s", pregunta)
            return {
                "respuesta": "Ocurrió un error generando la respuesta. Intenta nuevamente.",
                "citaciones": [],
                "documentos_encontrados": False,
            }

        if respuesta.rstrip(".!?") == "No lo sé":
            return {
                "respuesta": "No lo sé.",
                "citaciones": [],
                "documentos_encontrados": False,
            }

        return {
            "respuesta": respuesta,
            "citaciones": documentos_relacionados,
            "documentos_encontrados": True,
        }


# Instancia única reutilizada por toda la aplicación
_servicio_rag: ServicioRAG | None = None


def obtener_servicio_rag() -> ServicioRAG:
    global _servicio_rag
    if _servicio_rag is None:
        _servicio_rag = ServicioRAG()
        _servicio_rag.inicializar()
    return _servicio_rag


def busqueda_de_respuestas_rag(pregunta: str) -> Dict:
    """Punto de entrada simple usado por el resto del backend (agent.py)."""
    return obtener_servicio_rag().buscar_respuesta(pregunta)
