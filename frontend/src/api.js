// Cliente de la API de Django con renovación automática del token JWT.

const CLAVE_TOKENS = "mm_tokens";
let tokens = leerTokens();

function leerTokens() {
  try {
    return JSON.parse(localStorage.getItem(CLAVE_TOKENS)) || null;
  } catch {
    return null;
  }
}

export function guardarTokens(nuevos) {
  tokens = nuevos;
  try {
    if (nuevos) localStorage.setItem(CLAVE_TOKENS, JSON.stringify(nuevos));
    else localStorage.removeItem(CLAVE_TOKENS);
  } catch {
    // Sin almacenamiento (modo privado): la sesión dura lo que dure la pestaña.
  }
}

export const tokenDeAcceso = () => tokens?.access || null;
export const haySesion = () => Boolean(tokens?.access);

export class ErrorApi extends Error {
  constructor(estado, datos) {
    super(mensajeDeError(datos) || `Error ${estado}`);
    this.estado = estado;
    this.datos = datos;
  }
}

/** Primer mensaje legible dentro de una respuesta de error de DRF. */
export function mensajeDeError(datos) {
  if (!datos) return "";
  if (typeof datos === "string") return datos;
  if (Array.isArray(datos)) return mensajeDeError(datos[0]);
  if (datos.detail) return mensajeDeError(datos.detail);
  const primero = Object.values(datos)[0];
  return mensajeDeError(primero);
}

async function renovar() {
  const r = await fetch("/api/auth/token/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: tokens.refresh }),
  });
  if (!r.ok) return false;
  guardarTokens({ ...tokens, ...(await r.json()) });
  return true;
}

export async function api(ruta, { metodo = "GET", datos, formulario, crudo = false } = {}, reintento = true) {
  const headers = {};
  if (tokens?.access) headers.Authorization = `Bearer ${tokens.access}`;
  let body;
  if (formulario) {
    body = formulario;
  } else if (datos !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(datos);
  }

  const r = await fetch(ruta, { method: metodo, headers, body });
  if (r.status === 401 && tokens?.refresh && reintento) {
    if (await renovar()) return api(ruta, { metodo, datos, formulario, crudo }, false);
    guardarTokens(null);
    window.dispatchEvent(new Event("mm:sesion-vencida"));
  }
  if (!r.ok) throw new ErrorApi(r.status, await r.json().catch(() => null));
  if (crudo) return r;
  return r.status === 204 ? null : r.json();
}

export async function iniciarSesion(usuario, clave) {
  const r = await fetch("/api/auth/token/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: usuario, password: clave }),
  });
  if (!r.ok) throw new ErrorApi(r.status, { detail: "Usuario o clave incorrectos." });
  guardarTokens(await r.json());
}
