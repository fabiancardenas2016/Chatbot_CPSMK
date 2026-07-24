# Chatbot RR.HH. — Caja de Previsión Social Municipal de Karakura

# Para ver el proyecto desplegado visitar el enlace https://chatbot-cpsmk.onrender.com 
# Nota: en enlace https://chatbot-cpsmk.onrender.com puede tardar 30-60 segundos e incluso 
# un poco mas en "despertar" si nadie lo ha usado en un rato (15 min sin uso).

Asistente virtual que responde preguntas de Recursos Humanos usando **RAG**
(Retrieval-Augmented Generation) sobre los manuales oficiales de la entidad,
con un flujo de **triaje** (LangGraph) que decide si la pregunta se puede
resolver automáticamente, si falta información, o si debe abrirse un ticket.

Este proyecto es la versión organizada y lista para producción del notebook
`copia_de_challenge.py` (Google Colab), separado en un **backend** (API REST
con FastAPI) y un **frontend** (HTML/CSS/JS) desacoplados pero desplegables
como un único servicio.

## Árbol del proyecto

```
rrhh-chatbot/
├── backend/
│   ├── app.py              # API FastAPI (endpoints + sirve el frontend)
│   ├── agent.py             # Grafo LangGraph: triaje -> RAG / pedir_info / ticket
│   ├── rag.py                # Carga de PDF, índice FAISS, cadena de respuesta
│   ├── triaje.py             # Clasificación de la pregunta (LLM + salida estructurada)
│   ├── models.py             # Modelos Pydantic (request/response de la API)
│   ├── config.py             # Configuración centralizada (.env, logging, rutas)
│   ├── requirements.txt
│   ├── data/
│   │   ├── documentos/       # PDF de RR.HH. (colocar aquí los 4 documentos)
│   │   └── faiss_index/      # Índice vectorial persistido (se genera solo)
│   └── logs/                 # Logs de ejecución (se genera solo)
├── frontend/
│   ├── index.html            # Interfaz de chat
│   ├── style.css             # Estilos (incluye modo oscuro y diseño responsive)
│   └── script.js              # Lógica de conexión con el backend
├── deploy/
│   └── DESPLIEGUE_OCI.md     # Guía paso a paso para desplegar en Oracle Cloud
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── .dockerignore
```

## 1. Requisitos

- Python 3.11+
- Una clave gratuita de **Google AI Studio**: https://aistudio.google.com/apikey
  (usada tanto para el LLM de chat como para los embeddings, ambos en el
  nivel gratuito de Gemini).

## 2. Instalación local

```bash
cd rrhh-chatbot
cp .env.example .env
# Edita .env y coloca tu GOOGLE_API_KEY

cd backend
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Coloca los 4 PDF de RR.HH. en `backend/data/documentos/` (ver el archivo
`LEEME.txt` de esa carpeta; ya se incluye `RRHH-1-Resumen.pdf` como ejemplo).

## 3. Ejecutar en desarrollo

```bash
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Abre tu navegador en **http://localhost:8000** — el mismo servidor FastAPI
sirve el frontend y la API (`/api/preguntar`, `/api/salud`).

> La primera ejecución tarda un poco más porque construye el índice FAISS
> (genera embeddings de los PDF). Las siguientes ejecuciones cargan el
> índice ya guardado en `backend/data/faiss_index/`.

## 4. Ejecutar con Docker (recomendado para producción)

```bash
docker compose build
docker compose up -d
```

La aplicación queda disponible en **http://localhost** (puerto 80).

## 5. Endpoints de la API

| Método | Ruta              | Descripción                                   |
|--------|-------------------|------------------------------------------------|
| GET    | `/api/salud`      | Health check                                    |
| POST   | `/api/preguntar`  | Recibe `{ "pregunta": "..." }` y retorna la respuesta del agente |

Ejemplo de respuesta de `/api/preguntar`:

```json
{
  "pregunta": "¿Cuándo puedo solicitar una licencia de maternidad?",
  "respuesta": "Según el manual...",
  "decision": "AUTO_RESOLVER",
  "urgencia": "MEDIANA",
  "accion_final": "AUTO_RESOLVER",
  "citaciones": [
    {"documento": "RRHH-1-Resumen.pdf", "contenido": "..."}
  ],
  "es_ticket": false
}
```

## 6. Despliegue en Render 
#### Nota: 
El despliegue en Oracle Cloud Infrastructure (OCI) no fue posible por problemas de disponibilidad 
de capacidad pero se deja disponible guía completa en [`deploy/DESPLIEGUE_OCI.md`](deploy/DESPLIEGUE_OCI.md).

## 🚀 Demo en vivo 

Puedes probar el chatbot funcionando aquí: **[chatbot-cpsmk.onrender.com](https://chatbot-cpsmk.onrender.com)**

> ⚠️ Nota: el servicio corre en el plan gratuito de Render, que "duerme" tras 15
> minutos de inactividad. La primera pregunta después de un rato sin uso puede
> tardar entre 30 y 60 segundos o más mientras el servidor despierta.

![Vista del chatbot de RR.HH. de la CPSM Karakura](assets/chatbot-demo.png)

## 7. Notas de diseño

- **Costos**: se usan exclusivamente modelos gratuitos de Google AI Studio
  (`gemini-2.5-flash` para chat, `gemini-embedding-001` para embeddings).
  Puedes cambiarlos vía variables de entorno en `.env` sin tocar el código.
- **Persistencia del índice**: el índice FAISS se guarda en disco para no
  regenerar embeddings (y así no agotar la cuota gratuita) en cada reinicio.
- **Manejo de errores y logging**: cada módulo captura excepciones y registra
  eventos en `backend/logs/backend.log` y en consola.
- **Seguridad**: la clave de API nunca se expone al frontend; solo vive en el
  backend, cargada desde `.env` (excluido de git vía `.gitignore`).
