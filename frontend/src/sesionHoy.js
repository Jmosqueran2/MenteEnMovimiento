// Sesión preparada del día (modelo híbrido): el cuidador la deja lista en la
// pantalla 11 y el adulto mayor la empieza cuando quiere en la pantalla 03.
import { api } from "./api";

const ruta = (pacienteId, accion = "") => `/api/pacientes/${pacienteId}/${accion}`;

export const leerSesionHoy = (pacienteId) => api(ruta(pacienteId, "sesion-hoy/"));
export const comenzarSesionHoy = (pacienteId) => api(ruta(pacienteId, "sesion-hoy/comenzar/"), { metodo: "POST" });
export const terminarSesionHoy = (pacienteId) => api(ruta(pacienteId, "sesion-hoy/terminar/"), { metodo: "POST" });
export const prepararSesion = (pacienteId, datos) => api(ruta(pacienteId, "preparar/"), { metodo: "POST", datos });
export const pedirAyuda = (pacienteId, motivo) => api(ruta(pacienteId, "ayuda/"), { metodo: "POST", datos: { motivo } });
export const ayudaAtendida = (pacienteId) => api(ruta(pacienteId, "ayuda/atendida/"), { metodo: "POST" });

// «Iniciar ahora con [nombre]»: el cuidador está al lado. Vale para esta
// pestaña y se borra en la despedida.
const CLAVE_ACOMPANADO = "mm_acompanado";

export function marcarAcompanado(pacienteId) {
  try {
    if (pacienteId) sessionStorage.setItem(CLAVE_ACOMPANADO, String(pacienteId));
    else sessionStorage.removeItem(CLAVE_ACOMPANADO);
  } catch {
    // Sin almacenamiento: se trata como no acompañado.
  }
}

export function estaAcompanado(pacienteId) {
  try {
    return sessionStorage.getItem(CLAVE_ACOMPANADO) === String(pacienteId);
  } catch {
    return false;
  }
}
