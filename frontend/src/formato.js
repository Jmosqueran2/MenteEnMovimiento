const DIAS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

const mismoDia = (a, b) => a.toDateString() === b.toDateString();

/** "Hoy", "Ayer" o "Lun" (como en la tabla de seguimiento del prototipo). */
export function etiquetaDia(fechaIso) {
  const fecha = new Date(fechaIso);
  const hoy = new Date();
  const ayer = new Date(hoy);
  ayer.setDate(hoy.getDate() - 1);
  if (mismoDia(fecha, hoy)) return "Hoy";
  if (mismoDia(fecha, ayer)) return "Ayer";
  return DIAS[fecha.getDay()];
}

/** "Hoy, 10:30" */
export function fechaCorta(fechaIso) {
  const hora = new Date(fechaIso).toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${etiquetaDia(fechaIso)}, ${hora}`;
}

/** 4.2 → "4,2" */
export const decimal = (numero, digitos = 1) =>
  numero === null || numero === undefined
    ? "—"
    : numero.toLocaleString("es-EC", { minimumFractionDigits: digitos, maximumFractionDigits: digitos });

/** Fecha local en formato AAAA-MM-DD. */
export const hoyIso = () => new Date().toLocaleDateString("en-CA");

export const NOMBRE_ACTIVIDAD = {
  memoria: "Memoria",
  atencion: "Atención",
  coordinacion: "Coordinación",
  historia: "Mi Historia",
};

export const NOMBRE_NIVEL = { facil: "Fácil", medio: "Medio", dificil: "Difícil" };
export const ORDEN_NIVEL = ["facil", "medio", "dificil"];

/** "cuidador" o "cuidadora", según el perfil de la persona. */
export const rolCuidador = (paciente) => (paciente?.rol_cuidador === "cuidadora" ? "cuidadora" : "cuidador");

/** ["Memoria", "Atención", "Mi Historia"] → "Memoria, Atención y Mi Historia" */
export function enumerar(partes) {
  if (partes.length <= 1) return partes.join("");
  return `${partes.slice(0, -1).join(", ")} y ${partes.at(-1)}`;
}

/** "10:15" */
export const hora = (fechaIso) =>
  new Date(fechaIso).toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit", hour12: false });
