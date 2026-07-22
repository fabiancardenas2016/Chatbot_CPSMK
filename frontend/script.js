// script.js
// Lógica del frontend: envía la pregunta del usuario al backend (FastAPI),
// pinta el historial de la conversación y muestra citaciones / alertas de ticket.

// Si el frontend se sirve desde el mismo servidor que el backend (recomendado,
// vía StaticFiles en app.py), basta con una ruta relativa. Si se despliega el
// frontend por separado, cambia esta constante por la URL pública del backend,
// por ejemplo: "https://mi-servidor-oci.com/api"
const API_BASE_URL = "/api";

const chatHistorial = document.getElementById("chat-historial");
const form = document.getElementById("form-pregunta");
const input = document.getElementById("input-pregunta");
const btnPreguntar = document.getElementById("btn-preguntar");
const indicadorEscribiendo = document.getElementById("indicador-escribiendo");
const btnModoOscuro = document.getElementById("btn-modo-oscuro");

// ---------------------------------------------------------------------------
// Modo oscuro (persistido solo en memoria de la sesión, sin localStorage)
// ---------------------------------------------------------------------------
let modoOscuro = window.matchMedia("(prefers-color-scheme: dark)").matches;

function aplicarTema() {
  document.documentElement.setAttribute("data-tema", modoOscuro ? "oscuro" : "claro");
  btnModoOscuro.textContent = modoOscuro ? "☀️" : "🌙";
}
aplicarTema();

btnModoOscuro.addEventListener("click", () => {
  modoOscuro = !modoOscuro;
  aplicarTema();
});

// ---------------------------------------------------------------------------
// Utilidades de render
// ---------------------------------------------------------------------------
function escaparHTML(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}

function agregarMensajeUsuario(texto) {
  const mensaje = document.createElement("div");
  mensaje.className = "mensaje mensaje--usuario";
  mensaje.innerHTML = `<div class="mensaje__contenido">${escaparHTML(texto)}</div>`;
  chatHistorial.appendChild(mensaje);
  desplazarAlFinal();
}

function agregarMensajeBot(data) {
  const mensaje = document.createElement("div");
  mensaje.className = "mensaje mensaje--bot";

  const contenido = document.createElement("div");
  contenido.className = "mensaje__contenido";
  contenido.innerHTML = escaparHTML(data.respuesta);

  const meta = document.createElement("div");
  meta.className = "mensaje__meta";
  if (data.decision) {
    meta.innerHTML += `<span class="etiqueta">Decisión: ${escaparHTML(data.decision)}</span>`;
  }
  if (data.urgencia) {
    meta.innerHTML += `<span class="etiqueta">Urgencia: ${escaparHTML(data.urgencia)}</span>`;
  }
  if (data.accion_final) {
    meta.innerHTML += `<span class="etiqueta">Acción: ${escaparHTML(data.accion_final)}</span>`;
  }

  contenido.appendChild(meta);

  if (data.es_ticket) {
    const alerta = document.createElement("div");
    alerta.className = "alerta-ticket";
    alerta.textContent = "🎫 Se ha generado una solicitud de ticket para el área de RR.HH.";
    contenido.appendChild(alerta);
  }

  if (Array.isArray(data.citaciones) && data.citaciones.length > 0) {
    const detalle = document.createElement("details");
    detalle.className = "citaciones";
    const resumen = document.createElement("summary");
    resumen.textContent = `📄 Ver ${data.citaciones.length} citación(es) de los documentos`;
    detalle.appendChild(resumen);

    data.citaciones.forEach((cita, indice) => {
      const item = document.createElement("div");
      item.className = "citacion-item";
      item.innerHTML =
        `<strong>Citación ${indice + 1} — ${escaparHTML(cita.documento)}</strong><br>` +
        escaparHTML(cita.contenido);
      detalle.appendChild(item);
    });

    contenido.appendChild(detalle);
  }

  mensaje.appendChild(contenido);
  chatHistorial.appendChild(mensaje);
  desplazarAlFinal();
}

function agregarMensajeError(texto) {
  const mensaje = document.createElement("div");
  mensaje.className = "mensaje mensaje--bot";
  mensaje.innerHTML = `<div class="mensaje__contenido">⚠️ ${escaparHTML(texto)}</div>`;
  chatHistorial.appendChild(mensaje);
  desplazarAlFinal();
}

function desplazarAlFinal() {
  chatHistorial.scrollTop = chatHistorial.scrollHeight;
}

// ---------------------------------------------------------------------------
// Envío de preguntas al backend
// ---------------------------------------------------------------------------
async function enviarPregunta(pregunta) {
  indicadorEscribiendo.classList.remove("oculto");
  btnPreguntar.disabled = true;
  input.disabled = true;

  try {
    const respuesta = await fetch(`${API_BASE_URL}/preguntar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pregunta }),
    });

    if (!respuesta.ok) {
      const errorData = await respuesta.json().catch(() => ({}));
      throw new Error(errorData.detalle || `Error del servidor (${respuesta.status})`);
    }

    const data = await respuesta.json();
    agregarMensajeBot(data);
  } catch (error) {
    console.error("Error consultando el backend:", error);
    agregarMensajeError(
      "No fue posible obtener una respuesta. Verifica tu conexión e intenta nuevamente."
    );
  } finally {
    indicadorEscribiendo.classList.add("oculto");
    btnPreguntar.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (evento) => {
  evento.preventDefault();
  const pregunta = input.value.trim();
  if (!pregunta) return;

  agregarMensajeUsuario(pregunta);
  input.value = "";
  enviarPregunta(pregunta);
});
