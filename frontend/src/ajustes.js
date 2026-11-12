// Preferencias de este equipo (no viajan al servidor).
const POR_DEFECTO = {
  control: "camara", // "camara" | "mouse" (mouse: solo para pruebas sin cámara)
  voz: true, // narración de las instrucciones
  // Sensibilidad del cursor con la mano: depende de la cámara de cada equipo
  // (con poco ángulo o baja resolución conviene subirla).
  sensibilidad: 1,
  // Última persona a cargo elegida en este navegador (id).
  paciente: null,
  // Avisar en este equipo (notificación del navegador) cuando la persona termina.
  avisar: false,
  // Menú lateral del panel del cuidador escondido.
  menuOculto: false,
};

export function leerAjuste(clave) {
  try {
    const valor = localStorage.getItem(`mm_${clave}`);
    return valor === null ? POR_DEFECTO[clave] : JSON.parse(valor);
  } catch {
    return POR_DEFECTO[clave];
  }
}

export function guardarAjuste(clave, valor) {
  try {
    localStorage.setItem(`mm_${clave}`, JSON.stringify(valor));
  } catch {
    // Sin almacenamiento disponible: se usa el valor por defecto.
  }
}
